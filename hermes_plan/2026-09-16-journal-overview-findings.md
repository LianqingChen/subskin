# Findings

AssessmentVisualHome syncScene stores scrollTop/maxScroll progress. History loading changes maxScroll; multiplying by larger range pulls stack up even without user input. Fix default as viewport/layout-derived position while untouched. Keep absolute scroll after manual gestures; keep expanded panel pinned to end. Fit reference model in space above default panel on shorter portrait screens. Existing tablet/desktop and <=600px tall in-flow layouts remain.
