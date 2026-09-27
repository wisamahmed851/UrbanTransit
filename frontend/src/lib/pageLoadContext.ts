/** The page-load context and hook (see lib/pageLoad.tsx for the phases). */

import { createContext, useContext } from 'react'

export interface PageLoad {
 /** Loader dismissed and gone: entrance animations may run. */
 revealed: boolean
 /** Tracked data finished: the loader may leave. */
 ready: boolean
 /** Register a request made while the page is opening; call the returned function when it settles. */
 track: () => () => void
 /** Called by the loader when its exit animation has finished. */
 onLoaderGone: () => void
}

const done = () => {}

/** Outside a page (sign-in, public site) everything counts as loaded and revealed. */
export const PageLoadContext = createContext<PageLoad>({ revealed: true, ready: true, track: () => done, onLoaderGone: done })

export function usePageLoad() {
 return useContext(PageLoadContext)
}
