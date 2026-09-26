import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import json
import warnings

# Suppress sklearn warnings about feature names
warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "python"
FEATURES_DIR = PROJECT_ROOT / "colab_export" / "features"
REPORTS_DIR = PROJECT_ROOT / "reports"

class WhatIfSimulator:
    def __init__(self):
        # Load Phase 6/7 Models
        self.crowding_model = joblib.load(MODELS_DIR / "crowding_flag" / "xgboost_v1.pkl")
        self.crowding_prep = joblib.load(MODELS_DIR / "crowding_flag" / "xgboost_preprocessor_v1.pkl")
        
        self.delay_model = joblib.load(MODELS_DIR / "delay_severity" / "xgboost_v1.pkl")
        self.delay_prep = joblib.load(MODELS_DIR / "delay_severity" / "xgboost_preprocessor_v1.pkl")
        
        # Load baseline data
        self.trip_features = pd.read_parquet(FEATURES_DIR / "trip_features")
        
    def _get_base_row(self, route_id, time_period=None, hour=None):
        df = self.trip_features[self.trip_features['route_id'] == route_id]
        if df.empty:
            raise ValueError(f"No data for route {route_id}")
            
        if hour is None and time_period and "-" in time_period:
            try:
                hour = int(time_period.split(":")[0])
            except:
                pass
                
        if hour is not None:
            df_hour = df[df['hour'] == hour]
            if not df_hour.empty:
                df = df_hour
                
        # Return a representative row (mean for numerics, mode for categoricals)
        row = df.iloc[0].copy()
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                row[col] = df[col].mean()
            else:
                row[col] = df[col].mode()[0] if not df[col].mode().empty else row[col]
        
        # Ensure it's a 1-row dataframe for sklearn
        return pd.DataFrame([row])

    def simulate(self, scenario):
        s_type = scenario.get("type")
        route_id = scenario.get("route_id")
        
        result = {
            "scenario_type": s_type,
            "route_id": route_id,
            "confidence": "estimate",
            "warning_flags": []
        }
        
        if not route_id:
            result["warning_flags"].append("Missing route_id")
            return result
            
        try:
            time_period = scenario.get("time_period", "08:00-09:00")
            base_row = self._get_base_row(route_id, time_period)
            
            # Helper to predict crowding
            def predict_crowding(row):
                X = self.crowding_prep.transform(row)
                prob = self.crowding_model.predict_proba(X)[0][1]
                return prob
                
            # Helper to predict delay
            def predict_delay(row):
                X = self.delay_prep.transform(row)
                preds = self.delay_model.predict_proba(X)[0]
                # Delay classes are typically 0=On Time, 1=Minor, 2=Moderate, 3=Severe
                # Return probability of being Severe (index 3) or at least Moderate
                return float(preds[-1])

            if s_type == "increase_frequency":
                add_trips = scenario.get("additional_trips", 1)
                
                # Estimate new headway
                current_headway = base_row['headway_min'].values[0]
                # Rough approximation: if we add N trips per hour. Let's assume period is 1 hour
                current_trips = 60.0 / (current_headway if current_headway > 0 else 15)
                new_trips = current_trips + add_trips
                new_headway = 60.0 / new_trips
                
                result["estimated_new_headway_min"] = round(new_headway, 1)
                result["estimated_waiting_time_reduction_min"] = round((current_headway / 2) - (new_headway / 2), 1)
                
                # Estimate new crowding
                new_row = base_row.copy()
                new_row['headway_min'] = new_headway
                result["estimated_crowding_probability"] = round(float(predict_crowding(new_row)), 3)
                
                # Estimate demand coverage
                # Demand coverage improves as capacity increases
                cap_per_trip = base_row['capacity_total'].values[0]
                result["estimated_demand_coverage_improvement_passengers"] = int(add_trips * cap_per_trip * 0.8)

            elif s_type == "decrease_frequency":
                remove_trips = scenario.get("removed_trips", 1)
                
                current_headway = base_row['headway_min'].values[0]
                current_trips = 60.0 / (current_headway if current_headway > 0 else 15)
                new_trips = max(1.0, current_trips - remove_trips)
                new_headway = 60.0 / new_trips
                
                result["estimated_new_headway_min"] = round(new_headway, 1)
                result["estimated_waiting_time_increase_min"] = round((new_headway / 2) - (current_headway / 2), 1)
                
                new_row = base_row.copy()
                new_row['headway_min'] = new_headway
                new_prob = predict_crowding(new_row)
                result["estimated_crowding_probability"] = round(float(new_prob), 3)
                
                if new_prob > 0.85:
                    result["warning_flags"].append("New occupancy would likely exceed Critical threshold")

            elif s_type in ["add_vehicle", "change_vehicle_capacity"]:
                new_cap = scenario.get("new_capacity", 120)
                current_boardings = base_row['boardings'].values[0]
                
                new_occupancy_pct = min(1.0, current_boardings / new_cap)
                result["estimated_new_occupancy_pct"] = round(new_occupancy_pct, 2)
                
                new_row = base_row.copy()
                new_row['capacity_total'] = new_cap
                # Also set vehicle_type if applicable to influence the model
                if new_cap > 100:
                    new_row['vehicle_type'] = 'Articulated Bus'
                    
                new_prob = predict_crowding(new_row)
                result["estimated_crowding_probability"] = round(float(new_prob), 3)
                
                if new_occupancy_pct < 0.85:
                    result["warning_flags"].append("This resolves the Critical/Overcrowded condition")

            elif s_type == "shift_trip_time":
                shift_mins = scenario.get("shift_minutes", 15)
                
                current_hour = base_row['hour'].values[0]
                # Very simple heuristic: shift hour if > 30 mins
                new_hour = current_hour + (1 if shift_mins > 30 else (-1 if shift_mins < -30 else 0))
                
                new_row = base_row.copy()
                new_row['hour'] = new_hour
                new_row['peak_hour_indicator'] = 1 if new_hour in [7,8,9, 16,17,18] else 0
                new_row['peak_hour_indicator_asof'] = new_row['peak_hour_indicator']
                
                new_delay_risk = predict_delay(new_row)
                result["estimated_severe_delay_risk"] = round(float(new_delay_risk), 3)
                
                # Demand change using historical
                hist_demand = base_row['historical_demand_average'].values[0]
                result["estimated_demand_change"] = round(hist_demand * (1.1 if new_row['peak_hour_indicator'].values[0] else 0.8))

            elif s_type == "remove_low_demand_trip":
                current_occupancy = base_row['occupancy_pct'].values[0]
                if current_occupancy < 0.30:
                    result["warning_flags"].append("Trip is confirmed below Low occupancy threshold")
                else:
                    result["warning_flags"].append(f"Trip occupancy is {current_occupancy:.1%}, NOT below Low threshold")
                    
                boardings = base_row['boardings'].values[0]
                result["estimated_riders_affected"] = int(boardings)
                result["nearest_alternative_trip_min"] = round(base_row['headway_min'].values[0], 1)
                
                new_headway = base_row['headway_min'].values[0] * 2
                if new_headway > 30:
                    result["warning_flags"].append("Removal would create a gap above maximum headway (30+ min)")
                    
            else:
                result["warning_flags"].append(f"Unknown scenario type: {s_type}")
                
        except Exception as e:
            result["warning_flags"].append(f"Simulation error: {str(e)}")
            
        return result

def run_examples():
    sim = WhatIfSimulator()
    scenarios = [
        {
            "type": "increase_frequency",
            "route_id": "R012",
            "time_period": "08:00-09:00",
            "day_type": "weekday",
            "additional_trips": 2
        },
        {
            "type": "decrease_frequency",
            "route_id": "R014",
            "time_period": "14:00-15:00",
            "day_type": "weekday",
            "removed_trips": 1
        },
        {
            "type": "add_vehicle",
            "route_id": "R012",
            "time_period": "08:00-09:00",
            "new_capacity": 150
        },
        {
            "type": "change_vehicle_capacity",
            "route_id": "R025",
            "time_period": "09:00-10:00",
            "new_capacity": 100
        },
        {
            "type": "shift_trip_time",
            "route_id": "R030",
            "time_period": "17:00-18:00",
            "shift_minutes": 30
        },
        {
            "type": "remove_low_demand_trip",
            "route_id": "R102",
            "time_period": "22:00-23:00"
        }
    ]
    
    results = []
    for sc in scenarios:
        res = sim.simulate(sc)
        # merge scenario and result for display
        combined = {"scenario": sc, "result": res}
        results.append(combined)
        
    with open(REPORTS_DIR / "whatif_examples.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Saved {len(results)} What-If examples to {REPORTS_DIR / 'whatif_examples.json'}")

if __name__ == "__main__":
    run_examples()
