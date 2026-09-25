SELECT t.*, p.passenger_type, p.age_group, p.gender
FROM tickets t LEFT JOIN passengers p ON t.passenger_id = p.passenger_id
