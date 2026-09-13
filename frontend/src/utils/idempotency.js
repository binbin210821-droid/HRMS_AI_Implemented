export function generateIdempotencyKey() {
  return crypto.randomUUID()
}
