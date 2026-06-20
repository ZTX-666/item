function parseJson(text, label = 'JSON') {
  const raw = String(text || '').trim()
  try {
    return JSON.parse(raw)
  } catch {
    /* try extracting JSON below */
  }

  const objectStart = raw.indexOf('{')
  const objectEnd = raw.lastIndexOf('}')
  if (objectStart >= 0 && objectEnd > objectStart) {
    try {
      return JSON.parse(raw.slice(objectStart, objectEnd + 1))
    } catch {
      /* try array below */
    }
  }

  const arrayStart = raw.indexOf('[')
  const arrayEnd = raw.lastIndexOf(']')
  if (arrayStart >= 0 && arrayEnd > arrayStart) {
    try {
      return JSON.parse(raw.slice(arrayStart, arrayEnd + 1))
    } catch {
      /* fall through */
    }
  }

  throw new Error(`${label} 解析失败`)
}

module.exports = { parseJson }
