# Document intelligence hardening

This change set addresses the issues observed during the local DocuMind verification.

## Changes

- Upload UI now polls the document list for up to three minutes after the API accepts an upload. It reports a ready document only after observing `ready`, reports the worker's actual failure reason for `failed`, and otherwise says processing is still underway. On success it selects the uploaded document in chat.
- Explicit phrases such as "recently uploaded document", "latest uploaded file", and "document I just uploaded" resolve to the newest ready document in the current workspace when the user has not explicitly selected a document.
- An explicitly selected document continues to take precedence over inferred recent-document scope.
- The RAG system prompt now requires the model to inspect all supplied excerpts, acknowledge evidence that is present, distinguish explicit claims from inference, and avoid claiming that partial retrieved context represents the entire source.
- The worker retries Kafka client startup with bounded exponential backoff (2–30 seconds), rather than exiting immediately during a temporary broker interruption.
- Regression tests cover recent-document language, non-matching general questions, grounded-answer instructions, and retry classification.

## Verification still required locally

Run the backend test suite and frontend production build after pulling this branch. Then verify upload transitions from processing to ready, recent-upload language selects the latest ready document, and an explicitly selected document remains isolated.

This change does not implement persisted, hierarchical whole-document summaries. RAG still answers from its configured retrieved chunk set. A comprehensive analysis pipeline should be a separately tested feature rather than being represented as complete by this hardening change.
