# API Reference — Strategy REST / Mosaic Data Model

Official reference documentation: https://microstrategy.github.io/rest-api-docs/common-workflows/mosaic/
Interactive Swagger explorer on client environment: `{baseUrl}/api-docs/index.html`

`baseUrl` is typically formatted as `https://<host>/MicroStrategyLibrary`.

## 1. Authentication

`POST {baseUrl}/api/auth/login`

Headers: `Content-Type: application/json`
Body:
```json
{
  "username": "user",
  "password": "password",
  "loginMode": 1
}
```
- `loginMode`: 1 = Standard, 16 = LDAP, 4096 = SSO (confirm with environment administrator if non-standard).
- Response: HTTP 204, no response body. The session token is returned in the **response header** `X-MSTR-AuthToken`. This token must be passed in all subsequent requests within the `X-MSTR-AuthToken` header.
- Session cookies are also set; if the HTTP client does not persist cookies automatically, they must be manually forwarded.

Logout (close session, recommended upon task completion): `POST {baseUrl}/api/auth/logout` with the same token header.

## 2. Projects

`GET {baseUrl}/api/projects`
Headers: `X-MSTR-AuthToken`

Returns the list of **projects accessible to the authenticated user** (each containing `id`, `name`, `alias`, `description`, `status`). Use this to:
- Present available projects to the user when they do not know the exact project name or wish to inspect options.
- Resolve the `projectId` (GUID) from a supplied project name. This `projectId` must be provided in the `X-MSTR-ProjectID` header across all modeling/Mosaic API calls.

## 2.1 Locate a Mosaic Data Model ID by Name

When the user only knows the **name** of the Mosaic model (rather than the GUID `dataModelId`), use the API quick search rather than prompting for the ID manually:

`GET {baseUrl}/api/searches/results?name={query}&pattern=4&type=3&getAncestors=false&limit=-1&certifiedStatus=ALL`

Headers: `X-MSTR-AuthToken`, `X-MSTR-ProjectID`

- `type=3` — "report" object family (cubes and Mosaic Data Models belong to this family).
- `pattern=4` — denotes "contains" (case-insensitive search). Other values exist (e.g., 2=begins with, 1=exact), but 4 is optimal for free-text search.
- Response: `{ "totalItems": N, "result": [ { "id", "name", "type", "subtype", "description", "dateModified", "owner": {...} }, ... ] }`.
- **Filter by `subtype == 776`** in the result list — this is the specific subtype for Mosaic Data Models (EMMA cube / `report_emma_cube`). Other subtypes in the "report" family (768, 769, 770, 774, 777, etc.) represent conventional cubes or reports, not Mosaic models.
- The `id` field of each matching item is the `dataModelId` used in section 3 calls.

If search yields no results, try partial queries or broaden the search scope (`root` folder).

## 3. Data Model (Mosaic)

All endpoints below belong to the **Data Model** family and adhere to the path structure:
`{baseUrl}/api/model/dataModels/{dataModelId}/...`

Mandatory headers on all calls: `X-MSTR-AuthToken`, `X-MSTR-ProjectID`.
Optional header: `X-MSTR-MS-Changeset` (see section 5) to read or edit draft versions rather than published versions.

### 3.1 Model General Information
`GET /api/model/dataModels/{dataModelId}`

Returns: name, description, `schemaFolderId`, `dataServeMode`, `enableWrangleRecommendations`, `enableAutoHierarchyRelationships`, `sampling` (type/rows), `partition` (mode/count), `autoJoin`, `readOnly`.

### 3.2 Tables
- List: `GET /api/model/dataModels/{dataModelId}/tables?offset=0&limit=-1`
- Single table (including embedded attributes and metrics mapped to that table): `GET /api/model/dataModels/{dataModelId}/tables/{tableId}`

Each table object returns `physicalTable` (columns, data types, source pipeline — SQL, dataSourceId, physical name), lists of `attributes` and `factMetrics` using that table as lookup, and `refreshPolicy`.

### 3.3 Attributes
Follows a similar pattern to tables (verify on environment `api-docs` if path naming differs across versions):
- List: `GET /api/model/dataModels/{dataModelId}/attributes?offset=0&limit=-1`
- Single attribute: `GET /api/model/dataModels/{dataModelId}/attributes/{attributeId}`

Key fields: `information.name`, `forms[]` (each form: `formCategory.name`, `isKeyForm`, `lookupTable`, `expression.text`), `nonAggregatable`.

### 3.4 Facts / Base Metrics
- List: `GET /api/model/dataModels/{dataModelId}/baseMetrics?offset=0&limit=-1`
Key fields: name, expression (column/formula), source table.

### 3.5 Derived Metrics
- List: `GET /api/model/dataModels/{dataModelId}/metrics?offset=0&limit=-1`
Key fields: name, expression, `semanticRole`.

### 3.6 Hierarchies
- List: `GET /api/model/dataModels/{dataModelId}/hierarchy` (or `/hierarchies`, verify in environment api-docs — public documentation defines singular "hierarchy" per model with attribute relationships)
Key fields: member attributes and parent/child relationships (used for navigation/drilling).

### 3.7 Folders, Security Filters, Links, External Models, ACL, Translations
Follow the identical sub-resource path pattern under `dataModelId` (`/folders`, `/securityFilters`, `/links`, `/externalDataModels`, `/objects/{id}/acl`, `/objects/{id}/translations`). Only invoke if requested summary requires these details — not needed for standard model summaries.

## 4. Export (Reference only — NOT the primary mechanism used by this skill)
`POST /api/model/dataModels/{dataModelId}/export` produces an environment-specific YAML/package bundle. Re-importing externally modified export packages is not reliably supported — which is why this skill reads models via granular GET requests and performs targeted edits.

## 5. Changesets (Required when publishing modifications back to Strategy ONE)
1. `POST /api/model/changesets` with `{ "projectId": ... }` → returns a changeset `id`.
2. Pass this ID in the `X-MSTR-MS-Changeset` header across GET/PATCH/PUT/POST/DELETE calls on data model resources to work in draft mode without affecting the published version.
3. `POST /api/model/dataModels/{dataModelId}/publish` (within the changeset) to commit and publish changes once confirmed.
Reference: https://microstrategy.github.io/rest-api-docs/common-workflows/modeling/changesets

## 6. Common Errors
- 401: Expired token — re-authenticate.
- 403: Missing `X-MSTR-ProjectID` header or insufficient user privileges on project/model.
- 404 on dataModelId: Verify that the object is indeed a Mosaic Data Model (subType `report_emma_cube`) rather than a traditional report or cube.
