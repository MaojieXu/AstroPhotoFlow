// Compiler-derived symbols for the self-authored frontend, not HTTP DTOs.
import fs from 'node:fs'
import ts from 'typescript'
import { parse } from 'vue/compiler-sfc'

const paths = JSON.parse(fs.readFileSync(0, 'utf8'))
const output = {}
for (const path of paths) {
  const text = fs.readFileSync(path, 'utf8')
  const parts = path.endsWith('.vue')
    ? (() => { const { descriptor } = parse(text); return [descriptor.script, descriptor.scriptSetup].filter(Boolean).map(script => ({ text: script.content, offset: script.loc.start.line - 1 })) })()
    : [{ text, offset: 0 }]
  const result = { imports: [], functions: [] }
  for (const part of parts) {
    const source = ts.createSourceFile(path, part.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    function visit(node, scope = '') {
      if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        result.imports.push({ module: node.moduleSpecifier.text, type_only: Boolean(node.importClause?.isTypeOnly || node.isTypeOnly) })
      }
      if (ts.isFunctionLike(node) && node.body) {
        const position = source.getLineAndCharacterOfPosition(node.getStart(source))
        const name = node.name?.getText(source) ?? (ts.isVariableDeclaration(node.parent) || ts.isPropertyAssignment(node.parent) ? node.parent.name.getText(source) : `<callback@${position.line + 1}:${position.character + 1}>`)
        const qualified = scope + name
        const calls = []
        function collect(child) {
          if (ts.isCallExpression(child)) calls.push(child.expression.getText(source))
          ts.forEachChild(child, collect)
        }
        collect(node.body)
        result.functions.push({ name: qualified, line: part.offset + position.line + 1,
          end_line: part.offset + source.getLineAndCharacterOfPosition(node.getEnd()).line + 1,
          parameters: node.parameters.map(parameter => parameter.getText(source)),
          returns: node.type?.getText(source) ?? null,
          calls: [...new Set(calls)].sort() })
        ts.forEachChild(node, child => visit(child, qualified + '.'))
      } else ts.forEachChild(node, child => visit(child, scope))
    }
    visit(source)
  }
  output[path] = result
}
process.stdout.write(JSON.stringify(output))
