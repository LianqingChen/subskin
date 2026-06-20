# Medical Encyclopedia Website Design Patterns & Best Practices
## Research Synthesis: Mayo Clinic, WebMD, NHS, Wikipedia, VitePress

**Date**: April 2026  
**Focus**: Layout patterns, navigation, content hierarchy, accessibility for vitiligo knowledge base redesign

---

## 1. LAYOUT PATTERNS FROM TOP MEDICAL SITES

### 1.1 Mayo Clinic Pattern: Clean Authority + Alphabetical Navigation

**Key Features:**
- **Hero Section**: Clear value proposition ("Explore comprehensive guides on hundreds of conditions")
- **Alphabetical A-Z Filter**: Large, scannable letter buttons (A-Z) for quick condition lookup
- **Card-Based Grid**: Conditions organized in feature cards with consistent spacing
- **White Space**: Generous padding and margins reduce cognitive load
- **Typography Hierarchy**: Large, readable fonts (clamp-based responsive sizing)

**HTML Structure:**
```html
<!-- Hero Section -->
<div class="hero-section">
  <h1>Diseases & Conditions</h1>
  <p class="lede-text">Explore comprehensive guides on hundreds of common and rare diseases</p>
</div>

<!-- Alphabetical Navigation -->
<nav class="alpha-filter">
  <ol class="letter-list">
    <li><a href="#a">A</a></li>
    <li><a href="#b">B</a></li>
    <!-- ... Z -->
  </ol>
</nav>

<!-- Condition Cards -->
<div class="card-grid">
  <div class="card card--feature">
    <h2 id="a">A</h2>
    <ul class="condition-list">
      <li><a href="/conditions/acne/">Acne</a></li>
      <li><a href="/conditions/arthritis/">Arthritis</a></li>
    </ul>
  </div>
</div>
```

**Why It Works:**
- Alphabetical filtering reduces search friction
- Cards create visual rhythm and scanability
- Consistent spacing builds trust (medical authority)

---

### 1.2 NHS Pattern: Breadcrumb + Sidebar + Content Flow

**Key Features:**
- **Breadcrumb Navigation**: Home > Health A to Z > Conditions (shows context)
- **Primary Navigation**: Top-level categories (Health A-Z, NHS Services, Healthy Living, Mental Health)
- **A-Z Index with Anchors**: Jump links to letter sections on same page
- **Card-Based Sections**: Each letter grouped in a card with border
- **Back-to-Top Links**: After each section for long pages

**HTML Structure:**
```html
<!-- Breadcrumb -->
<nav class="breadcrumb">
  <ol>
    <li><a href="/">Home</a></li>
    <li><a href="/health-a-to-z/">Health A to Z</a></li>
    <li>Conditions A to Z</li>
  </ol>
</nav>

<!-- A-Z Navigation with Anchors -->
<nav id="nhsuk-nav-a-z" role="navigation">
  <ol class="letter-nav">
    <li><a href="#a">A</a></li>
    <li><a href="#b">B</a></li>
  </ol>
</nav>

<!-- Sectioned Cards -->
<div class="card card--feature">
  <h2 id="a">A</h2>
  <ul class="condition-list nhsuk-list--border">
    <li><a href="/conditions/acne/">Acne</a></li>
  </ul>
</div>

<!-- Back to Top -->
<a href="#nhsuk-nav-a-z" class="back-to-top">Back to top</a>
```

**Why It Works:**
- Breadcrumbs provide context and escape routes
- Anchor-based navigation is fast (no page reload)
- Grouped sections reduce scrolling fatigue

---

### 1.3 WebMD Pattern: Tabbed Content + Multiple Entry Points

**Key Features:**
- **Multiple Content Types**: Health A-Z Reference, Features, Slideshows, Quizzes, Videos
- **Tabs/Sections**: Different ways to consume the same information
- **Sidebar Recommendations**: "Top doctors in [location]", related links
- **Search-First UX**: Prominent search bar with autocomplete
- **Pill Identifier & Tools**: Interactive utilities (drug search, symptom checker)

**Why It Works:**
- Multiple entry points serve different user intents
- Tools (pill identifier, symptom checker) build engagement
- Tabs reduce page length while maintaining comprehensiveness

---

## 2. CONTENT HIERARCHY: CONDITION → SYMPTOMS → DIAGNOSIS → TREATMENT

### 2.1 Wikipedia Medical Article Structure (Gold Standard)

Wikipedia's medical article structure is proven for patient education:

```markdown
# [Condition Name]

## Infobox (Right Sidebar)
- Specialty
- Symptoms
- Onset
- Duration
- Causes
- Risk factors
- Diagnostic method
- Treatment
- Prognosis
- Frequency
- Deaths

## Overview / Introduction
- 1-2 sentence definition
- Who it affects
- Why it matters

## Signs and Symptoms
- Early signs
- Common symptoms
- Severity variations
- When to seek help

## Causes
- Primary causes
- Risk factors
- Epidemiology (who gets it)

## Diagnosis
- Diagnostic criteria
- Tests and procedures
- Differential diagnosis

## Treatment
- First-line treatments
- Alternative treatments
- Prognosis and outcomes

## Prevention
- Primary prevention
- Secondary prevention

## Epidemiology
- Prevalence
- Incidence
- Geographic variation

## History
- Discovery
- Evolution of treatment

## Society and Culture
- Social impact
- Stigma
- Notable cases

## See Also / References
```

**Key Principle**: Answer the most common patient questions in order:
1. "What is this?" (Definition)
2. "Do I have it?" (Symptoms)
3. "How do I know for sure?" (Diagnosis)
4. "What can I do?" (Treatment)
5. "Will I be okay?" (Prognosis)

---

### 2.2 Medical Condition Page Schema (Schema.org Best Practice)

For AI discoverability and rich results:

```json
{
  "@context": "https://schema.org",
  "@type": "MedicalWebPage",
  "about": {
    "@type": "MedicalCondition",
    "name": "Vitiligo",
    "alternateName": ["白癜风", "Leucoderma"],
    "description": "A skin condition causing loss of skin pigmentation",
    "symptom": [
      "White patches on skin",
      "Loss of color in hair",
      "Loss of color in mucous membranes"
    ],
    "cause": "Autoimmune destruction of melanocytes",
    "riskFactor": [
      "Family history",
      "Autoimmune diseases",
      "Thyroid disorders"
    ],
    "possibleTreatment": [
      "Topical corticosteroids",
      "JAK inhibitors",
      "Phototherapy",
      "Surgical grafting"
    ],
    "epidemiology": "Affects 0.5-2% of global population",
    "prognosis": "Chronic but manageable condition"
  },
  "author": {
    "@type": "Organization",
    "name": "SubSkin Medical Encyclopedia"
  },
  "datePublished": "2026-04-14",
  "dateModified": "2026-04-14"
}
```

---

## 3. NAVIGATION PATTERNS: INTUITIVE DISCOVERY

### 3.1 Breadcrumb + Sidebar + Cross-Links (Recommended for VitePress)

```
Home > Conditions > Skin Diseases > Vitiligo
                                    ↓
                    [Main Content Area]
                    ├─ Definition
                    ├─ Symptoms
                    ├─ Diagnosis
                    ├─ Treatment
                    └─ Related Conditions
                       ├─ Alopecia Areata
                       ├─ Psoriasis
                       └─ Lichen Planus
```

**VitePress Implementation:**

```typescript
// .vitepress/config.ts
export default defineConfig({
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Conditions', link: '/conditions/' },
      { text: 'Treatments', link: '/treatments/' },
      { text: 'Research', link: '/research/' }
    ],
    sidebar: {
      '/conditions/': [
        {
          text: 'Skin Conditions',
          items: [
            { text: 'Vitiligo', link: '/conditions/vitiligo/' },
            { text: 'Psoriasis', link: '/conditions/psoriasis/' },
            { text: 'Eczema', link: '/conditions/eczema/' }
          ]
        },
        {
          text: 'Autoimmune Diseases',
          items: [
            { text: 'Lupus', link: '/conditions/lupus/' },
            { text: 'Rheumatoid Arthritis', link: '/conditions/ra/' }
          ]
        }
      ]
    }
  }
})
```

### 3.2 Index Page: Card Grid + Category Navigation

**Pattern**: Show major categories as cards, each with icon + description

```vue
<!-- docs/conditions/index.md -->
---
layout: home
---

<div class="condition-categories">
  <div class="category-card">
    <div class="icon">🔬</div>
    <h3>Skin Conditions</h3>
    <p>Dermatological disorders affecting pigmentation and appearance</p>
    <a href="/conditions/skin/">Browse →</a>
  </div>
  
  <div class="category-card">
    <div class="icon">🛡️</div>
    <h3>Autoimmune Diseases</h3>
    <p>Conditions where the immune system attacks the body</p>
    <a href="/conditions/autoimmune/">Browse →</a>
  </div>
  
  <div class="category-card">
    <div class="icon">💊</div>
    <h3>Treatments & Therapies</h3>
    <p>Evidence-based treatment options and clinical trials</p>
    <a href="/treatments/">Browse →</a>
  </div>
</div>
```

---

## 4. CATEGORY ORGANIZATION: INDEX PAGE PATTERNS

### 4.1 Card Grid with Icons (Recommended)

**Advantages:**
- Visual scanning is faster than text lists
- Icons create memorable associations
- Scalable to many categories

```html
<div class="grid grid-cols-3 gap-6">
  <a href="/conditions/skin/" class="card">
    <div class="icon-circle">🔬</div>
    <h3>Skin Conditions</h3>
    <p>Vitiligo, psoriasis, eczema, and more</p>
  </a>
  
  <a href="/treatments/" class="card">
    <div class="icon-circle">💊</div>
    <h3>Treatments</h3>
    <p>JAK inhibitors, topical therapies, phototherapy</p>
  </a>
  
  <a href="/research/" class="card">
    <div class="icon-circle">📊</div>
    <h3>Research</h3>
    <p>Latest clinical trials and drug development</p>
  </a>
</div>
```

### 4.2 Alphabetical Index (For Large Condition Lists)

**When to use**: 50+ conditions

```html
<nav class="alpha-index">
  <div class="letter-buttons">
    <a href="#a" class="letter">A</a>
    <a href="#b" class="letter">B</a>
    <!-- ... -->
  </div>
  
  <div id="a" class="letter-section">
    <h2>A</h2>
    <ul>
      <li><a href="/conditions/acne/">Acne</a></li>
      <li><a href="/conditions/alopecia/">Alopecia Areata</a></li>
    </ul>
  </div>
</nav>
```

### 4.3 Hierarchical Sidebar (For Deep Content)

**When to use**: Complex taxonomy (e.g., Skin Conditions > Pigmentation Disorders > Depigmentation)

```typescript
sidebar: {
  '/conditions/': [
    {
      text: 'Skin Conditions',
      collapsed: false,
      items: [
        {
          text: 'Pigmentation Disorders',
          items: [
            { text: 'Vitiligo', link: '/conditions/vitiligo/' },
            { text: 'Melasma', link: '/conditions/melasma/' }
          ]
        },
        {
          text: 'Inflammatory Conditions',
          items: [
            { text: 'Psoriasis', link: '/conditions/psoriasis/' },
            { text: 'Eczema', link: '/conditions/eczema/' }
          ]
        }
      ]
    }
  ]
}
```

---

## 5. ACCESSIBILITY & READABILITY STANDARDS

### 5.1 WCAG 2.2 Level AA Compliance (NHS Standard)

**Typography:**
- Minimum font size: 16px (body text)
- Line height: 1.5 or greater
- Line length: 50-75 characters (optimal reading width)
- Font family: Sans-serif (Frutiger, Helvetica, Arial)

```css
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  max-width: 75ch; /* Character-based width limit */
  color: #222;
}

h1 { font-size: clamp(28px, 5vw, 48px); }
h2 { font-size: clamp(24px, 4vw, 36px); }
h3 { font-size: clamp(20px, 3vw, 28px); }
```

**Color Contrast:**
- Text on background: 4.5:1 minimum (AA)
- Large text (18pt+): 3:1 minimum
- Interactive elements: 3:1 minimum

**Keyboard Navigation:**
- All interactive elements must be keyboard accessible
- Focus indicators must be visible (3px outline minimum)
- Tab order must be logical

```css
:focus {
  outline: 3px solid #005eb8;
  outline-offset: 2px;
}
```

**Landmarks (ARIA):**
```html
<header role="banner">...</header>
<nav role="navigation" aria-label="Primary navigation">...</nav>
<main id="maincontent">...</main>
<aside role="complementary">...</aside>
<footer role="contentinfo">...</footer>
```

### 5.2 Mobile Responsiveness

**Breakpoints:**
- Mobile: 320px - 640px
- Tablet: 641px - 1024px
- Desktop: 1025px+

**Touch Targets:**
- Minimum 44x44px (WCAG 2.5.5)
- Spacing between targets: 8px minimum

```css
a, button {
  min-height: 44px;
  min-width: 44px;
  padding: 12px 16px;
}
```

### 5.3 Content Readability

**Plain Language:**
- Avoid jargon; explain medical terms
- Use active voice
- Short sentences (15-20 words average)
- Bullet points for lists

**Example (Before/After):**
```
❌ BEFORE: "Vitiligo is characterized by the progressive depigmentation of the epidermis due to melanocyte dysfunction."

✅ AFTER: "Vitiligo causes white patches on the skin. This happens when the body stops making melanin (the pigment that gives skin its color)."
```

**Headings:**
- Use semantic hierarchy (H1 > H2 > H3)
- Never skip levels (don't jump from H1 to H3)
- Make headings descriptive

```markdown
# Vitiligo (H1 - Page title)

## What is Vitiligo? (H2 - Main sections)

### Early Signs (H3 - Subsections)

### When to See a Doctor (H3)

## Diagnosis (H2)

### Blood Tests (H3)
```

---

## 6. VITEPRESS MEDICAL SITE EXAMPLES & PATTERNS

### 6.1 VitePress Configuration for Medical Content

```typescript
// docs/.vitepress/config.ts
import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'SubSkin Medical Encyclopedia',
  description: 'Evidence-based vitiligo knowledge base',
  
  themeConfig: {
    // Search configuration
    search: {
      provider: 'local', // Built-in MiniSearch
      options: {
        miniSearch: {
          options: {
            processTerm: (term) => term.toLowerCase()
          }
        }
      }
    },
    
    // Navigation
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Conditions', link: '/conditions/' },
      { text: 'Treatments', link: '/treatments/' },
      { text: 'Research', link: '/research/' },
      { text: 'About', link: '/about/' }
    ],
    
    // Sidebar with medical hierarchy
    sidebar: {
      '/conditions/': [
        {
          text: 'Skin Conditions',
          items: [
            { text: 'Vitiligo Overview', link: '/conditions/vitiligo/' },
            { text: 'Symptoms & Signs', link: '/conditions/vitiligo/symptoms/' },
            { text: 'Diagnosis', link: '/conditions/vitiligo/diagnosis/' },
            { text: 'Treatment Options', link: '/conditions/vitiligo/treatment/' }
          ]
        }
      ],
      '/treatments/': [
        {
          text: 'Topical Treatments',
          items: [
            { text: 'Corticosteroids', link: '/treatments/topical/corticosteroids/' },
            { text: 'Calcineurin Inhibitors', link: '/treatments/topical/calcineurin/' }
          ]
        },
        {
          text: 'Systemic Treatments',
          items: [
            { text: 'JAK Inhibitors', link: '/treatments/systemic/jak-inhibitors/' },
            { text: 'Phototherapy', link: '/treatments/systemic/phototherapy/' }
          ]
        }
      ]
    },
    
    // Social links
    socialLinks: [
      { icon: 'github', link: 'https://github.com/subskin' },
      { icon: 'twitter', link: 'https://twitter.com/subskin' }
    ]
  }
})
```

### 6.2 Medical Condition Page Template

```markdown
---
title: Vitiligo
description: Comprehensive guide to vitiligo, including symptoms, diagnosis, and treatment options
layout: doc
---

# Vitiligo (白癜风)

> **Medical Disclaimer**: This information is for educational purposes only and does not constitute medical advice. Always consult with a healthcare provider for diagnosis and treatment.

## Quick Facts

| Property | Value |
|----------|-------|
| **Also Known As** | Leucoderma, Leukoderma |
| **Affects** | 0.5-2% of global population |
| **Type** | Autoimmune skin condition |
| **Onset** | Usually before age 40 |
| **Prognosis** | Chronic but manageable |

## What is Vitiligo?

Vitiligo is a skin condition that causes white patches to appear on the skin. This happens when the body stops making melanin—the pigment that gives skin its color.

**Key points:**
- Affects people of all skin types
- Not contagious
- Can be emotionally challenging due to visible appearance
- Multiple treatment options available

## Symptoms & Signs

### Early Signs
- Small white patches (macules) on the skin
- Usually appears on hands, feet, face, or lips
- Patches may spread over time

### Common Symptoms
- Loss of skin color in patches
- Premature whitening of hair in affected areas
- Loss of color in mucous membranes (mouth, nose)
- Sensitivity to sun exposure in affected areas

### When to See a Doctor
- If you notice white patches appearing on your skin
- If patches are spreading
- If you're experiencing emotional distress

## Causes & Risk Factors

### What Causes Vitiligo?

The exact cause is unknown, but research suggests:
- **Autoimmune dysfunction**: The immune system attacks melanocytes (pigment-producing cells)
- **Genetic factors**: Family history increases risk
- **Environmental triggers**: Sun exposure, stress, skin trauma

### Risk Factors
- Family history of vitiligo (30-40% of cases)
- Other autoimmune diseases (thyroid, lupus, diabetes)
- Skin trauma or injury
- Emotional stress
- Certain medications

## Diagnosis

### How is Vitiligo Diagnosed?

**Clinical Examination:**
- Visual inspection under normal and UV light
- Wood's lamp examination (shows depigmented areas more clearly)

**Tests:**
- Skin biopsy (if diagnosis is unclear)
- Blood tests (to check for autoimmune conditions)
- Thyroid function tests

### Differential Diagnosis
- Pityriasis alba
- Tinea versicolor
- Ash leaf spots (tuberous sclerosis)
- Lichen sclerosus

## Treatment Options

### First-Line Treatments

**Topical Corticosteroids**
- Most common first treatment
- Applied directly to affected areas
- Effectiveness varies by location and skin type
- Potential side effects with long-term use

**Topical Calcineurin Inhibitors**
- Tacrolimus, pimecrolimus
- Useful for facial vitiligo
- No skin atrophy risk (unlike steroids)

### Systemic Treatments

**JAK Inhibitors** (Emerging)
- Ruxolitinib (FDA approved 2022)
- Shows promise in clinical trials
- Oral or topical formulations

**Phototherapy**
- Narrowband UVB (NB-UVB)
- PUVA (psoralen + UVA)
- Excimer laser
- Requires multiple sessions

### Surgical Options
- Skin grafting
- Melanocyte transplantation
- For stable, localized vitiligo

### Supportive Care
- Sunscreen (SPF 50+)
- Cosmetic camouflage
- Psychological support

## Prognosis & Outcomes

- **Course**: Unpredictable; may stabilize or progress
- **Remission**: Spontaneous repigmentation occurs in 10-15% of cases
- **Quality of Life**: Varies; emotional impact can be significant
- **Treatment Response**: 75% of patients show improvement with treatment

## Prevention

### Primary Prevention
- No proven prevention methods
- Avoid known triggers (stress, trauma)

### Secondary Prevention
- Early treatment may slow progression
- Sun protection prevents further damage
- Stress management

## Living with Vitiligo

### Emotional Support
- Support groups (online and in-person)
- Counseling for body image concerns
- Community resources

### Practical Tips
- Use high-SPF sunscreen daily
- Wear protective clothing
- Consider cosmetic options (makeup, tattooing)
- Connect with others with vitiligo

## Latest Research

### Clinical Trials
- JAK inhibitor trials showing 75% repigmentation rates
- Combination therapy approaches
- Stem cell research

### Emerging Treatments
- Oral JAK inhibitors
- Combination topical therapies
- Immunomodulatory approaches

## Related Conditions

- [Alopecia Areata](/conditions/alopecia-areata/) - Similar autoimmune mechanism
- [Psoriasis](/conditions/psoriasis/) - Other autoimmune skin condition
- [Thyroid Disorders](/conditions/thyroid/) - Common comorbidity

## References & Sources

- [PubMed: Vitiligo Research](https://pubmed.ncbi.nlm.nih.gov/?term=vitiligo)
- [Mayo Clinic: Vitiligo](https://www.mayoclinic.org/diseases-conditions/vitiligo/)
- [NHS: Vitiligo](https://www.nhs.uk/conditions/vitiligo/)
- [American Academy of Dermatology](https://www.aad.org/)

---

**Last Updated**: April 2026  
**Medical Review**: Pending specialist review  
**Disclaimer**: This page is for educational purposes. Always consult healthcare providers for medical decisions.
```

### 6.3 Custom Vue Component for Medical Content

```vue
<!-- docs/.vitepress/theme/components/MedicalConditionCard.vue -->
<template>
  <div class="medical-card">
    <div class="card-header">
      <h3>{{ title }}</h3>
      <span v-if="severity" class="severity-badge" :class="`severity-${severity}`">
        {{ severity }}
      </span>
    </div>
    
    <div class="card-content">
      <slot></slot>
    </div>
    
    <div class="card-footer">
      <a v-if="learnMoreLink" :href="learnMoreLink" class="learn-more">
        Learn More →
      </a>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: String,
  severity: {
    type: String,
    validator: (v) => ['mild', 'moderate', 'severe'].includes(v)
  },
  learnMoreLink: String
})
</script>

<style scoped>
.medical-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  margin: 16px 0;
  background: #fafafa;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.severity-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.severity-mild { background: #e8f5e9; color: #2e7d32; }
.severity-moderate { background: #fff3e0; color: #e65100; }
.severity-severe { background: #ffebee; color: #c62828; }

.learn-more {
  color: #005eb8;
  text-decoration: none;
  font-weight: 600;
}

.learn-more:hover {
  text-decoration: underline;
}
</style>
```

---

## 7. IMPLEMENTATION CHECKLIST FOR SUBSKIN REDESIGN

### Phase 1: Information Architecture
- [ ] Define condition taxonomy (skin conditions, autoimmune, treatments, research)
- [ ] Create content hierarchy template (Definition → Symptoms → Diagnosis → Treatment)
- [ ] Plan sidebar structure (3-4 levels maximum)
- [ ] Design index page with category cards

### Phase 2: VitePress Setup
- [ ] Configure sidebar navigation with medical hierarchy
- [ ] Set up search with medical terminology
- [ ] Create condition page template with frontmatter
- [ ] Implement breadcrumb component

### Phase 3: Accessibility
- [ ] Audit typography (16px minimum, 1.6 line-height)
- [ ] Test color contrast (4.5:1 for body text)
- [ ] Verify keyboard navigation
- [ ] Add ARIA landmarks
- [ ] Test with screen readers

### Phase 4: Content Structure
- [ ] Create medical condition template with schema.org markup
- [ ] Write condition pages following Wikipedia structure
- [ ] Add cross-links between related conditions
- [ ] Include medical disclaimers

### Phase 5: User Experience
- [ ] Implement A-Z index for large condition lists
- [ ] Add "Related Conditions" section
- [ ] Create treatment comparison tables
- [ ] Add "When to See a Doctor" callouts

---

## 8. KEY TAKEAWAYS

| Aspect | Best Practice |
|--------|---------------|
| **Layout** | Clean, white-space-heavy design with card grids |
| **Navigation** | Breadcrumbs + sidebar + A-Z index for large lists |
| **Content Order** | Definition → Symptoms → Diagnosis → Treatment → Prognosis |
| **Typography** | 16px+ sans-serif, 1.6 line-height, 50-75ch width |
| **Accessibility** | WCAG 2.2 AA, 4.5:1 contrast, keyboard navigation |
| **Mobile** | 44x44px touch targets, responsive typography |
| **Schema** | MedicalCondition + MedicalWebPage markup |
| **Search** | Alphabetical filtering + full-text search |
| **Trust Signals** | Medical disclaimers, source citations, expert review dates |

---

## 9. REFERENCES

- Mayo Clinic Design System: https://mayoclinic.org/diseases-conditions
- NHS Digital Service Manual: https://service-manual.nhs.uk/design-system
- Wikipedia Medical Article Guidelines: https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Medicine-related_articles
- Schema.org Medical Types: https://schema.org/MedicalCondition
- VitePress Documentation: https://vitepress.dev
- WCAG 2.2 Guidelines: https://www.w3.org/WAI/WCAG22/quickref/
- Healthcare Web Design 2026: https://unicornplatform.com/blog/healthcare-web-design-in-2026/

