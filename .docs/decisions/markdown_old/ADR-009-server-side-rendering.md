# ADR-009: Server-Side Rendering (Jinja2)

## Status

**Status:** Accepted
**Date:** 2026-02-13
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote frontend must achieve WCAG 2.1 Level AA accessibility compliance as a mandatory project requirement. The rendering approach (client-side SPA vs server-side rendering) fundamentally affects the baseline accessibility of the application, the development effort required to achieve compliance, and the voter experience (first paint time, JavaScript dependency, mobile performance).

### Background

The project proposal identifies accessibility as one of three critical barriers to adoption for online voting systems. Target users include voters with visual, auditory, motor, and cognitive impairments, as well as elderly voters with low digital literacy. The voting interface is primarily form-based — voters receive an email link, see a list of candidates, select one, and submit.

A prototype React SPA was built during Iteration 2 (§6.2.3 of Investigation Log) and tested for accessibility. The experiment revealed significant issues with screen reader compatibility, focus management, and first paint time — problems that are inherent to client-side rendering.

### Requirements

- **R1:** WCAG 2.1 Level AA compliance (mandatory project requirement)
- **R2:** Screen reader compatibility (NVDA, VoiceOver, JAWS)
- **R3:** Full keyboard navigation without mouse
- **R4:** Fast first contentful paint (<1 second from email click)
- **R5:** Works without JavaScript enabled (core voting flow)
- **R6:** Mobile-responsive design (voters access via email on phones)
- **R7:** Minimal build toolchain (no Webpack/Vite/Node.js in build process)
- **R8:** Integrated deployment (same container as backend service)

### Constraints

- **C1:** Single developer — cannot maintain separate frontend and backend codebases
- **C2:** No dedicated frontend developer or designer
- **C3:** WCAG AA compliance is non-negotiable (module and project requirement)
- **C4:** Voters arrive from email links — first paint must be fast

---

## Options Considered

### Option 1: React SPA

**Description:**
Single-page application using React with client-side rendering. API calls to backend services for data.

**Pros:**
- Rich interactivity (real-time updates, smooth transitions)
- Component-based architecture
- Large ecosystem (Material UI, React Router)
- Industry-standard frontend framework

**Cons:**
- Requires JavaScript for all functionality (fails R5)
- Screen reader announcements delayed until JS executes
- Focus management must be manually implemented for every page transition
- First Contentful Paint delayed by JS bundle download + parse + execute (~2.5s measured)
- Requires separate build toolchain (Webpack/Vite, Node.js)
- Creates separate deployment artefact (nginx container for static files)
- CORS configuration needed between frontend container and backend services
- Extensive ARIA attributes required for accessibility parity with SSR

**Evaluation:**
Fails R4 (first paint was 2.5s in prototype) and R5 (requires JavaScript). Would require significant additional effort for R1 (WCAG AA) and R2 (screen reader compatibility). The React prototype experiment (§6.2.3) confirmed these issues.

### Option 2: Vue.js SPA

**Description:**
Single-page application using Vue.js with a simpler API than React.

**Pros:**
- Simpler than React (less boilerplate)
- Good documentation with accessibility guide
- Progressive framework (can be adopted incrementally)

**Cons:**
- Same fundamental issues as React (JS dependency, delayed first paint, manual focus management)
- Same build toolchain requirements
- Same accessibility engineering burden

**Evaluation:**
Vue.js has the same structural limitations as React for accessibility. The simpler API reduces development time slightly but does not address the fundamental SSR vs CSR trade-offs.

### Option 3: Server-Side Rendering with Jinja2 — Chosen

**Description:**
HTML rendered on the server using Jinja2 templates integrated with FastAPI (via Starlette). The browser receives fully-formed HTML that works without JavaScript.

**Pros:**
- Works without JavaScript enabled (R5)
- Screen reader announces page content immediately on load
- Browser-native focus management on page navigation (correct by default)
- Standard HTML form POST for vote submission (no JS event handlers needed)
- Fast first contentful paint (~400ms — HTML already rendered by server)
- No build toolchain required (Jinja2 is pure Python)
- Integrated deployment (same container as backend service)
- Minimal ARIA attributes needed (semantic HTML elements are inherently accessible)
- Mobile-responsive via CSS media queries (no JS framework dependency)

**Cons:**
- Less interactive UI (full page reload on navigation)
- No client-side state management (each page is a fresh request)
- Older technology perception ("not modern")
- Limited real-time features without JavaScript additions

**Evaluation:**
Meets all requirements (R1–R8). The trade-off of reduced interactivity is acceptable for a voting system, which is fundamentally a form-submission application.

### Option 4: Static Site with API Calls

**Description:**
Pre-built static HTML files with JavaScript fetch() calls to backend APIs for dynamic data.

**Pros:**
- Good performance (CDN-cacheable static files)
- Simple deployment (static file server)

**Cons:**
- Requires JavaScript for any dynamic content (fails R5)
- Accessibility concerns with dynamically loaded content
- Separate deployment from backend services
- CORS configuration required

**Evaluation:**
A hybrid that inherits the worst aspects of both approaches — static HTML that breaks without JavaScript, but without the interactivity benefits of a full SPA.

---

## Decision

**Chosen Option:** Server-Side Rendering with Jinja2 (Option 3)

**Rationale:**
The decisive factor was WCAG AA compliance. SSR provides **inherent accessibility** that SPAs must engineer manually. The comparison table from §3.5.3 of the Investigation Log shows:

| Feature | SSR (Jinja2) | React/Vue SPA |
|---------|-------------|---------------|
| Works without JavaScript | Yes | No |
| Screen reader on load | Immediate | After JS executes |
| Focus management | Browser default (correct) | Must implement manually |
| Form submission without JS | Standard HTML POST | Requires JS handlers |
| First Contentful Paint | ~400ms | ~2,500ms |
| ARIA attributes needed | Minimal | Extensive |

**Key Factors:**

1. **Accessibility (R1, R2, R3):** Server-rendered HTML with semantic elements (`<form>`, `<label>`, `<button>`, `<fieldset>`) is inherently accessible. Screen readers work correctly without ARIA enhancements. Keyboard navigation follows natural tab order. This is not achievable with SPAs without significant engineering effort.

2. **First paint (R4):** 400ms (SSR) vs 2,500ms (React). Voters arriving from email links on mobile devices need fast page loads. A 2.5-second delay on a 3G connection could exceed 5 seconds — causing voter abandonment.

3. **Development efficiency (C1, C2):** A single developer maintaining Jinja2 templates is dramatically simpler than maintaining a React codebase with Webpack, state management, routing, ARIA attributes, and a separate build pipeline.

4. **Deployment simplicity (R8):** Templates are bundled into the same Docker image as the FastAPI application. No separate nginx container, no CORS, no API URL configuration.

---

## Consequences

### Positive Consequences

- **Inherent accessibility:** Semantic HTML provides screen reader support, keyboard navigation, and focus management without additional code
- **Fast first paint:** ~400ms from click to visible content — critical for mobile voters
- **No JavaScript dependency:** Core voting flow works with JavaScript disabled
- **Simple deployment:** Single container per service includes both API and templates
- **Developer efficiency:** No build toolchain, no state management library, no routing library

### Negative Consequences

- **Limited interactivity:** Full page reloads on navigation. Mitigated by: voting is a 3-step linear flow (verify identity → see ballot → submit vote) — page reloads are natural transitions.
- **Perceived as "old-fashioned":** SSR is less trendy than React/Vue. Mitigated by: the technology choice serves the user, not fashion trends. Accessibility is more important than developer perception.
- **No client-side validation:** Form validation occurs on the server (full round-trip for error messages). Mitigated by: can add progressive enhancement JavaScript for client-side validation without breaking the base SSR experience.

### Trade-offs Accepted

- **Interactivity vs Accessibility:** Accepted less interactive UI (page reloads) in exchange for inherent WCAG AA compliance. A voting system is fundamentally a form — it does not benefit from SPA interactivity (no drag-and-drop, no real-time updates during vote casting, no complex state management).
- **Modern appeal vs Development speed:** Accepted a "less modern" technology perception in exchange for 50%+ reduction in frontend development time (no Webpack, no state management, no ARIA engineering).

---

## Implementation Notes

### Technical Details

Template structure:
```
templates/
├── base.html              # Base layout (nav, footer, accessibility features)
├── verify_identity.html   # DOB verification form
├── vote.html              # Ballot with candidate options
├── vote_success.html      # Confirmation with receipt token
├── vote_error.html        # Error messages
└── vote_verified.html     # Receipt verification page
```

Accessibility features in base template:
- `lang="en"` on `<html>` element
- Skip navigation link for keyboard users
- Minimum 4.5:1 contrast ratio for all text
- Focus indicators on all interactive elements
- Semantic elements (`<main>`, `<nav>`, `<form>`, `<label>`, `<fieldset>`)
- ARIA live regions for dynamic status messages

### Configuration

- **Template engine:** Jinja2 via Starlette's `Jinja2Templates`
- **Static files:** Served via Starlette's `StaticFiles` middleware
- **CSS:** Custom stylesheet with responsive breakpoints
- **No JavaScript build:** Templates use plain HTML + CSS

### Integration Points

- **ADR-001 (FastAPI):** Templates rendered by FastAPI route handlers
- **ADR-008 (Microservices):** Frontend-service and voting-service each have their own templates
- **ADR-005 (Tokens):** Voting flow starts with token in URL, rendered in template form

---

## Validation

### Success Criteria

- [x] All pages render without JavaScript enabled
- [x] Screen reader (NVDA) correctly announces all page content
- [x] Keyboard navigation works (Tab, Shift+Tab, Enter, Space)
- [x] Colour contrast ≥ 4.5:1 for all text
- [x] First contentful paint < 1 second on localhost
- [x] Vote submission works via standard HTML form POST
- [x] Templates responsive on mobile (320px–1920px viewports)

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| First Contentful Paint | <1,000ms | ~400ms |
| WCAG AA compliance | 100% | Targeting 100% (audit pending) |
| JS dependency for voting | None | None (works with JS disabled) |
| Template count | As needed | 10 templates across services |

### Review Date

End of Stage 2 (April 2026) — conduct formal WCAG AA audit with automated tools (axe, Lighthouse) and manual screen reader testing.

---

## References

- [Investigation Log §3.5](../INVESTIGATION-LOG.md#35-frontend-approach-investigation) — Full evaluation
- [Investigation Log §6.2.3](../INVESTIGATION-LOG.md#623-failed-react-frontend-with-separate-build) — Failed React experiment
- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [ADR-001](ADR-001-python-fastapi-backend.md) — FastAPI with Jinja2 support
- [ADR-008](ADR-008-microservices-architecture.md) — Service structure

## Notes

Progressive enhancement JavaScript may be added in Stage 2 for non-essential features (client-side form validation, loading indicators) that enhance but do not replace the server-rendered base experience.
