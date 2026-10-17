# Task {{task_title}}

## Original Request

{{original_request}}

## Overview

{{ Problem statement, scope, and the key decisions you made. Surface the technical
   decisions you made silently, so reviewers can audit them. }}

## Implementation Plan

### Phase 1: {{ phase title }}

**Files to modify / create:**
- `path/to/file.ext` — {{ what changes }}

{{ Step-by-step changes, with snippets, before/after, or rationale where useful. }}

### Phase 2: {{ phase title }}

{{ Repeat as needed. Order phases so each one is a chunk a reviewer can verify on
   its own. }}

## Testing Strategy

### Unit tests
- {{ test files and what each one covers }}

### Manual QA
- **Tool:** {{ curl, a CLI invocation, a browser driver, a direct job or script run, DB/log inspection, etc. }}
- **Setup and safety:** {{ exact isolated data, environment, side-effect controls, and cleanup }}
- **Scenario:** {{ precise steps that execute the changed behaviour }}
- **Expected evidence:** {{ observable output, persisted state, logs, or rendered behaviour }}

{{ If genuinely not applicable, write "Not needed" followed by a task-specific
   explanation of why this change has no runtime behaviour to verify. }}

## To-Do List

### Implementation
- [ ] {{ implementation step 1 }}
- [ ] {{ implementation step 2 }}

### Testing
- [ ] {{ automated tests }}
- [ ] {{ manual QA scenario }}

## Project Docs Update

{{ Note any project documentation that needs updating, or write "Not needed for this change." }}

## Review Findings

<!-- bottega-kit writes this section from the reviewer's final message. Edits here are replaced. -->

## Verdict

<!-- bottega-kit writes this section from the judge's final message. Edits here are replaced. -->
