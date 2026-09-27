/**
 * Route loader (CMD-027): a progress bar along the top of the content area and a spinner ring
 * around the logo. It stays until the page's data has loaded (lib/pageLoad.tsx), fades out, and
 * only when it has gone does the page's entrance start. Transform/opacity only. With reduced
 * motion the bar and ring hold still and the fade is short: the loader is feedback, so it stays.
 */

import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { usePageLoad } from '../lib/pageLoadContext'

export function PageLoader() {
 const { ready, onLoaderGone } = usePageLoad()
 const reduce = useReducedMotion()
 return (
  <AnimatePresence onExitComplete={onLoaderGone}>
   {!ready && (
    <motion.div
     key="loader"
     className="page-loader"
     role="status"
     aria-live="polite"
     initial={{ opacity: 0 }}
     animate={{ opacity: 1, transition: { duration: 0.15 } }}
     exit={{ opacity: 0, transition: { duration: reduce ? 0.1 : 0.25 } }}
    >
     <span className="page-loader-bar" aria-hidden="true"><i /></span>
     <span className="page-loader-mark" aria-hidden="true">
      <img src="/logo-64.png" alt="" width={40} height={40} />
      <i className="page-loader-ring" />
     </span>
     <span className="sr-only">Loading the page</span>
    </motion.div>
   )}
  </AnimatePresence>
 )
}
