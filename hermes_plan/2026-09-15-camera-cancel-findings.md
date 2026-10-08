# Findings
continueRecord immediately resets result/upload and switches screen to capture before the camera opens. Closing its v-model therefore leaves the empty upload screen. The camera currently emits the same close signal before successful captured events, so cancellation must have a separate semantic event.
