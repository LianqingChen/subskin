/**
 * SubSkin Custom VitePress Theme
 *
 * Extends default VitePress theme with our custom medical-tech design system.
 */

import DefaultTheme from 'vitepress/theme'
import './custom.css'
import VASIAssessment from './components/VASIAssessment.vue'

export default {
  ...DefaultTheme,
  enhanceApp({ app }) {
    app.component('VASIAssessment', VASIAssessment)
  },
}
