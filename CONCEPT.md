# QATAKI

Concept and architecture.

QATAKI is a workbench for designing REST and GUI tests together with an AI agent. The result is a readable, tool-agnostic test description that the agent translates into an executable target. The name carries its three pillars: Quality Assurance, Test Automation, and AI.

## Why not just an AI coding assistant

You can already point a general AI agent at a website or a REST API, have it probe the system, and produce a test. The limitation is not capability, it is persistence. With a general assistant every session starts from zero: the format has to be re-explained, throwaway glue and ad-hoc skills are written each time, and the working context has to be rebuilt and defended against its own limits.

QATAKI removes that. It encodes the format, the workflow, the project context, and a reusable knowledge base once. When a project is opened, the agent already knows them. The agent itself is a commodity; the value is the persistent context and the maintained artifacts around it.

## Outcome

Two paths produce the same kind of artifact:

1. Authoring. In dialogue with the agent, REST and GUI tests are designed. The output is a test description in two files (below), not a generated script.
2. Ingestion. Existing Playwright scripts, including recorder and codegen output, are read in, analysed, reviewed with the author, and lifted into the same format.

The durable result is a maintained, reusable, tool-agnostic test description per project, from which executable tests are generated on demand.

## Architecture

### Two artifacts

`.feature` (Gherkin): the high-level behaviour of a scenario. Readable, standard Gherkin, and the durable tool-agnostic asset.

`.steps` (table): the concrete execution per step as `Action | Data | Expected`. This is a knowledge base. Once it is known how to perform a step against a given target, it is stored and reused across scenarios. It is a step-definition library held as agent-maintained data instead of hand-written glue.

The two files stay separate and are never nested, to keep both readable.

Example:

```gherkin
# login.feature
Scenario: Successful login
  Given the user is on the login page
  When the user logs in
  Then the dashboard is shown
```

```
# login.steps  (step "When the user logs in")
| Action                          | Data               | Expected                       |
| open /login                     |                    | login form visible             |
| find role=textbox name="User"   | user@example.com   |                                |
| find role=textbox name="Pass"   | <secret:login_pw>  |                                |
| find role=button  name="Submit" |                    | redirect /dashboard, token set |
```

### Principles

The agent owns both files and is always the translator. There are no hand-maintained step definitions and no glue code to keep in sync. A single hand keeps `.feature` and `.steps` consistent.

Universal verbs, neutral targets. Step actions use the universal interaction verbs that every automation tool shares (open, find, click, fill, and so on) with a neutral target descriptor (`role`, `name`, `text`, `testid`). The executable tool is only a renderer of this. The tool-specific flavour lives solely in how an element is addressed, never in the verb.

The agnostic boundary is the `.feature`. Targeting a different execution tool means regenerating `.steps` from the `.feature`, not keeping `.steps` neutral. The `.feature` is the lasting agnostic asset.

MCP-native agent. Capabilities are loaded as MCP servers, including the ability to probe the target so that `.steps` can be filled correctly. Playwright is integrated as the GUI step vocabulary and execution target, not as a recorder.

Secrets and parameters are tokens in the `Data` column (`<secret:…>`, `${baseUrl}`), resolved at execution time.

### Pipeline

```
.feature   intent       designed in dialogue, written by the agent
   |
.steps     execution    filled by the agent by probing the target   (knowledge base)
   |
target     executable   rendered by the agent: Playwright for GUI, a REST helper library for REST
```

Ingestion runs the same pipeline in reverse: an existing script maps near-mechanically to `.steps`, while the `.feature` is inferred and confirmed with the author.

### Scope

The first milestone is authoring and ingestion into `.feature` + `.steps` per project. Translation to an executable target and execution follow as a second milestone.
