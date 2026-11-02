/** Equivalent JSON Schema form supported by the pinned generator's IR. */
export function normalizeJsonValue(document: Record<string, unknown>): Record<string, unknown> {
  const components = document.components
  if (typeof components !== 'object' || components === null || !('schemas' in components)) return document
  const schemas = components.schemas
  if (typeof schemas !== 'object' || schemas === null || !('JsonValue' in schemas)) return document
  const value = schemas.JsonValue
  if (typeof value !== 'object' || value === null || Object.keys(value).length !== 0) return document
  // Pydantic emits {} for JsonValue. Both forms describe every JSON value,
  // but explicit recursion also gives the pinned generator a useful TS type.
  const reference = { $ref: '#/components/schemas/JsonValue' }
  return {
    ...document,
    components: {
      ...components,
      schemas: {
        ...schemas,
        JsonValue: {
          anyOf: [
            { type: 'string' }, { type: 'number' }, { type: 'boolean' }, { type: 'null' },
            { type: 'array', items: reference },
            { type: 'object', additionalProperties: reference }
          ]
        }
      }
    }
  }
}

export function normalizeEnumMaps(
  value: Record<string, unknown>
): Record<string, unknown>
export function normalizeEnumMaps(value: unknown): unknown
export function normalizeEnumMaps(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalizeEnumMaps)
  if (typeof value !== 'object' || value === null) return value
  const node = Object.fromEntries(
    Object.entries(value).map(([key, child]) => [key, normalizeEnumMaps(child)])
  )
  const names = node.propertyNames
  if (
    typeof names !== 'object' ||
    names === null ||
    !('enum' in names) ||
    !Array.isArray(names.enum) ||
    !names.enum.every((key): key is string => typeof key === 'string') ||
    node.properties !== undefined ||
    typeof node.additionalProperties !== 'object' ||
    node.additionalProperties === null
  )
    return node
  const { propertyNames: _names, additionalProperties: item, ...rest } = node
  return {
    ...rest,
    properties: Object.fromEntries(names.enum.map((key) => [key, item])),
    additionalProperties: false
  }
}
