已按 `skill2-build` 的标准做 scope 判断。以下是设计草案，不改文件。

**Scope 判断**

这是一个适合做 **顶层 agent skill** 的能力：`api-docs-manager`。

理由：它是跨项目复用的工作流，目标是让 agent 在维护 API 文档时遵守稳定流程：先找事实来源，再判断变更范围，再同步 OpenAPI/Markdown/示例/变更记录，而不是凭记忆改文档。

不建议拆成项目级 skill，除非某个 repo 有强绑定规范，比如固定文档站、私有 OpenAPI 生成器、内部 lint 命令。  
暂时不需要 `scripts/`，除非后续要固定执行 OpenAPI 校验、示例请求校验或文档站构建。  
可以后续拆 `references/`，但第一版 `SKILL.md` 足够。

**SKILL.md**我没懂，我看了下这个结构，我不知道这是在干嘛。

```markdown
---
name: api-docs-manager
description: Use when creating, updating, auditing, or reorganizing API documentation, including OpenAPI specs, endpoint reference docs, request/response examples, auth docs, changelogs, and docs generated from source code.
---

# API Docs Manager

Use this skill when the user asks to manage API documentation.

## Scope First

Before editing, classify the request as one of:

- `new-docs`: create docs for an existing API.
- `sync-docs`: update docs to match code, OpenAPI, tests, or recent changes.
- `audit-docs`: find missing, stale, inconsistent, or misleading API docs.
- `restructure-docs`: reorganize existing docs without changing API behavior.
- `not-docs`: API implementation, SDK generation, product copy, or support content that is not primarily API documentation.

If the source of truth is unclear, identify likely sources and ask only for the missing fact that blocks correctness.

## Source Of Truth

Prefer sources in this order, when available:

1. OpenAPI / Swagger specs.
2. Route handlers, controllers, schemas, validators, serializers, and auth middleware.
3. API tests, fixtures, cassettes, and example clients.
4. Existing docs and changelogs.
5. User-provided notes.

Do not invent endpoints, parameters, status codes, auth rules, rate limits, or response fields.

If docs and code disagree, report the disagreement and treat code/spec/tests as stronger than prose unless the user says otherwise.

## Documentation Rules

For each endpoint, verify or provide:

- Method and path.
- Purpose.
- Authentication and authorization requirements.
- Path, query, header, and body parameters.
- Required versus optional fields.
- Request examples.
- Success response examples.
- Error responses and status codes.
- Pagination, filtering, sorting, idempotency, and rate limit behavior when relevant.
- Versioning or deprecation notes when relevant.

Keep examples minimal but realistic. Use stable placeholder values. Avoid secrets, real tokens, private hostnames, and personal data.

## OpenAPI Rules

When editing OpenAPI:

- Preserve existing style, ordering, naming, and component reuse.
- Reuse schemas, parameters, responses, and security schemes when appropriate.
- Keep examples valid against schemas.
- Update shared components only when the behavior is shared.
- Avoid broad rewrites unless the user asks for reorganization.

## Markdown Rules

When editing Markdown docs:

- Preserve the existing information architecture unless restructuring is requested.
- Keep reference docs scannable.
- Prefer tables for parameter lists.
- Prefer fenced code blocks for examples.
- Keep prose factual and behavior-focused.
- Do not add marketing language.

## Change Handling

For sync or audit work:

1. List changed or affected endpoints.
2. Identify stale, missing, or contradictory docs.
3. Make the smallest documentation changes that restore accuracy.
4. Update changelog or migration notes only when the repo already uses them or the user asks.
5. Run available docs/spec validation commands when practical.

## Output

When reporting work, include:

- Scope classification.
- Source of truth used.
- Files or sections changed, if edits were made.
- Validation performed or not performed.
- Remaining uncertainties.
```

**测试场景**

```yaml
name: api-docs-manager
cases:
  - name: sync_docs_from_route_change
    prompt: >
      Update the API docs for the new PATCH /v1/users/{id} route.
      The implementation is already in the repo.
    expect:
      triggers_skill: true
      scope: sync-docs
      assertions:
        - Agent inspects route/controller/schema/test files before writing docs.
        - Agent documents method, path, auth, params, request body, responses, and errors.
        - Agent does not invent fields that are absent from code or schema.
        - Agent reports source of truth and validation performed.

  - name: audit_openapi_against_code
    prompt: >
      Check whether our OpenAPI spec is stale after the billing API changes.
    expect:
      triggers_skill: true
      scope: audit-docs
      assertions:
        - Agent compares OpenAPI with billing routes, schemas, and tests.
        - Agent lists mismatches by endpoint.
        - Agent distinguishes confirmed bugs from uncertainties.
        - Agent does not rewrite unrelated OpenAPI sections.

  - name: create_docs_for_existing_api
    prompt: >
      Create reference docs for the existing invite endpoints.
    expect:
      triggers_skill: true
      scope: new-docs
      assertions:
        - Agent identifies existing invite endpoints from source files.
        - Agent follows the repo's existing docs structure.
        - Agent includes request and response examples without secrets.
        - Agent asks a blocking question if auth or rate limits cannot be determined.

  - name: restructure_without_behavior_change
    prompt: >
      Reorganize the REST API docs so authentication, pagination, and errors are easier to find.
    expect:
      triggers_skill: true
      scope: restructure-docs
      assertions:
        - Agent preserves API facts and avoids behavior changes.
        - Agent keeps endpoint reference content intact unless moving it.
        - Agent summarizes the new information architecture.
        - Agent validates links or notes when link checking is unavailable.

  - name: adjacent_sdk_generation
    prompt: >
      Generate a TypeScript SDK from our OpenAPI file.
    expect:
      triggers_skill: false
      scope: not-docs
      assertions:
        - Agent recognizes this is SDK generation, not API documentation management.
        - Agent may inspect OpenAPI only as input to SDK work.
        - Agent does not apply docs-specific markdown rules unnecessarily.

  - name: implementation_not_docs
    prompt: >
      Add a new POST /v1/projects endpoint to the API.
    expect:
      triggers_skill: false
      scope: not-docs
      assertions:
        - Agent treats this as API implementation work.
        - Agent may suggest docs updates as follow-up only after implementation.
        - Agent does not start by writing documentation.
```

这版 skill 的边界比较清楚：它负责“让 API 文档准确、完整、可验证”，不负责设计 API、本体实现或 SDK 生成。