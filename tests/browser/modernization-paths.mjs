const stage = process.env.APF_REPORT_STAGE ?? 'g2'
if (!/^g[0-7]$/.test(stage)) throw new Error('Invalid modernization report stage')
export const reportRoot = new URL(`../../.artifacts/reports/modernization/${stage}/`, import.meta.url)
export const seedRoot = new URL('../../.artifacts/reports/modernization/g2/', import.meta.url)
