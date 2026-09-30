"""Rebuild the authored fixture corpus. Never executes the JavaScript."""
from pathlib import Path
import json
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
CASES = []


def pair(cwe, name, title, before, after, rationale, assumptions):
    CASES.append((cwe, name, title, textwrap.dedent(before).strip(), textwrap.dedent(after).strip(), rationale, assumptions))


pair("79", "message", "A message in the DOM", '''
function renderMessage(input, target) {
  target.innerHTML = input;
}''', '''
function renderMessage(input, target) {
  target.textContent = input;
}''', "textContent avoids interpreting untrusted text as HTML at this sink.", "The intended output is plain text; target is an existing DOM element.")
pair("79", "greeting", "A personalised greeting", '''
function greet(input, target) {
  target.insertAdjacentHTML('beforeend', '<p>' + input + '</p>');
}''', '''
function greet(input, target) {
  const paragraph = document.createElement('p');
  paragraph.textContent = input;
  target.appendChild(paragraph);
}''', "DOM construction keeps the untrusted greeting out of an HTML parser.", "A text-only paragraph is intended; document and target are trusted DOM objects.")
pair("79", "caption", "Replacing a caption", '''
function caption(input, target) {
  target.outerHTML = '<span>' + input + '</span>';
}''', '''
function caption(input, target) {
  const replacement = document.createElement('span');
  replacement.appendChild(document.createTextNode(input));
  target.replaceWith(replacement);
}''', "A text node preserves the caption without treating its content as markup.", "input is a string; replacement with a plain span matches the required behaviour.")
pair("79", "document", "Writing a document title", '''
function titleDocument(input, target) {
  target.write('<h1>' + input + '</h1>');
}''', '''
function titleDocument(input, target) {
  const heading = target.createElement('h1');
  heading.textContent = input;
  target.body.appendChild(heading);
}''', "The document title is inserted as text instead of concatenated HTML.", "target is an already loaded Document with a body; adding a heading is the intended behaviour.")

pair("89", "lookup", "Looking up a user", '''
async function findUser(input, db) {
  return db.query("SELECT id FROM users WHERE name = '" + input + "'");
}''', '''
async function findUser(input, db) {
  return db.query('SELECT id FROM users WHERE name = $1', [input]);
}''', "A bound value cannot alter the SQL structure at this query location.", "db implements node-postgres parameter binding; identifiers are fixed and authorisation is handled separately.")
pair("89", "search", "Searching a product catalogue", '''
async function searchProducts(input, db) {
  const sql = "SELECT sku FROM products WHERE title LIKE '%" + input + "%'";
  return db.query(sql);
}''', '''
async function searchProducts(input, db) {
  const sql = 'SELECT sku FROM products WHERE title LIKE $1';
  return db.query(sql, ['%' + input + '%']);
}''', "Parameter binding separates the pattern value from executable query syntax.", "node-postgres is used; wildcard interpretation is intentional and search authorisation is outside this example.")
pair("89", "delete", "Deleting an item by identifier", '''
async function removeItem(input, db) {
  return db.query('DELETE FROM items WHERE id = ' + input);
}''', '''
async function removeItem(input, db) {
  return db.query('DELETE FROM items WHERE id = $1', [input]);
}''', "Binding the identifier as a value prevents it from extending the DELETE statement.", "node-postgres binding and upstream ownership checks are assumed; this only addresses SQL injection.")
pair("89", "sort", "Choosing a sort direction", '''
async function sortedUsers(input, db) {
  return db.query('SELECT name FROM users ORDER BY name ' + input);
}''', '''
async function sortedUsers(input, db) {
  const direction = input === 'desc' ? 'DESC' : 'ASC';
  return db.query('SELECT name FROM users ORDER BY name ' + direction);
}''', "Only fixed direction tokens can reach the SQL statement.", "Only ascending and descending order are valid product options; column and table identifiers are fixed.")

pair("78", "checksum", "Computing a file checksum", '''
function checksum(input, childProcess) {
  return childProcess.execSync('sha256sum ' + input);
}''', '''
function checksum(input, childProcess) {
  return childProcess.execFileSync('sha256sum', ['--', input]);
}''', "execFileSync passes the filename without a shell, and -- ends command options.", "GNU sha256sum is installed; access to the file is authorised elsewhere; only shell injection is addressed.")
pair("78", "metadata", "Reading file metadata", '''
function metadata(input, childProcess) {
  return childProcess.execSync('stat ' + input);
}''', '''
function metadata(input, childProcess) {
  return childProcess.execFileSync('stat', ['--', input]);
}''', "The executable receives an argument array instead of a shell command string.", "GNU stat is used; -- is supported; the caller is allowed to inspect the selected file.")
pair("78", "hostname", "Resolving a selected host", '''
function resolveHost(input, childProcess) {
  return childProcess.execSync('getent hosts ' + input);
}''', '''
function resolveHost(input, childProcess) {
  if (!/^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$/.test(input)) {
    throw new Error('Invalid hostname');
  }
  return childProcess.execFileSync('getent', ['hosts', input]);
}''', "A restricted hostname and an argument-array API avoid shell interpretation and option-like input.", "A trusted getent executable is installed; DNS access policy and resource limits are handled separately.")
pair("78", "listing", "Listing a selected directory", '''
function listDirectory(input, childProcess) {
  return childProcess.execSync('ls -l ' + input);
}''', '''
function listDirectory(input, childProcess) {
  return childProcess.execFileSync('ls', ['-l', '--', input]);
}''', "Separating arguments removes shell metacharacter interpretation at this call.", "GNU ls is used; directory access is authorised separately. The example is scoped to command injection.")

pair("22", "document", "Reading a document by name", '''
function readDocument(input, fs, path, base) {
  return fs.readFileSync(path.join(base, input), 'utf8');
}''', '''
function readDocument(input, fs, path, base) {
  const root = fs.realpathSync(base);
  const file = fs.realpathSync(path.resolve(root, input));
  if (!file.startsWith(root + path.sep)) throw new Error('Outside root');
  return fs.readFileSync(file, 'utf8');
}''', "Canonical path containment prevents escape through .., absolute paths and already-existing symlinks.", "base is not a filesystem root; the directory tree cannot be changed by an attacker between check and read; regular files only.")
pair("22", "template", "Loading a named template", '''
function loadTemplate(input, fs, templateRoot) {
  return fs.readFileSync(templateRoot + '/' + input + '.html', 'utf8');
}''', '''
function loadTemplate(input, fs, templateRoot) {
  const templates = { welcome: 'welcome.html', receipt: 'receipt.html' };
  if (!Object.hasOwn(templates, input)) throw new Error('Unknown template');
  return fs.readFileSync(templateRoot + '/' + templates[input], 'utf8');
}''', "An own-property allowlist prevents input from constructing a filesystem path.", "Only the two listed templates are supported; their files and templateRoot are trusted and not symlinks to private files.")
pair("22", "avatar", "Loading an avatar file", '''
function readAvatar(input, fs, path, avatarRoot) {
  return fs.readFileSync(path.resolve(avatarRoot, input));
}''', '''
function readAvatar(input, fs, path, avatarRoot) {
  if (!/^[a-f0-9]{32}\\.png$/.test(input)) throw new Error('Invalid avatar id');
  return fs.readFileSync(path.join(avatarRoot, input));
}''', "A fixed filename grammar excludes path components and absolute-path forms.", "The avatar directory contains only trusted regular files with these names and no attacker-controlled symlinks.")
pair("22", "archive", "Selecting an archived report", '''
function readReport(input, fs, path, archive) {
  const file = path.resolve(archive, input);
  return fs.readFileSync(file);
}''', '''
function readReport(input, fs, path, archive) {
  const root = fs.realpathSync(archive);
  const file = fs.realpathSync(path.resolve(root, input));
  const relative = path.relative(root, file);
  if (!relative || relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
    throw new Error('Outside archive');
  }
  return fs.readFileSync(file);
}''', "The canonical relative path is checked against parent traversal and cross-volume absolute paths.", "The archive tree is immutable to untrusted actors during the read; the chosen file is otherwise authorised.")

pair("1321", "settings", "Updating a nested setting", '''
function updateSetting(input, value) {
  const settings = { theme: {} };
  settings[input].enabled = value;
  return settings;
}''', '''
function updateSetting(input, value) {
  if (input !== 'theme') throw new Error('Unknown setting');
  return { theme: { enabled: value } };
}''', "Restricting the key prevents inherited prototype objects from becoming a mutation target.", "Only the theme setting is valid; changing the accepted API to this schema is intentional.")
pair("1321", "merge", "Copying preferences into an object", '''
function copyPreferences(input, target) {
  return Object.assign(target, input);
}''', '''
function copyPreferences(input, target) {
  for (const key of ['theme', 'density']) {
    if (Object.hasOwn(input, key)) target[key] = input[key];
  }
  return target;
}''', "A fixed own-key schema prevents special prototype keys from being assigned.", "input is an untrusted plain parsed object; target is a normal object; theme and density are data fields without setters.")
pair("1321", "dictionary", "Building a preference dictionary", '''
function dictionary(input) {
  const result = {};
  for (const key of Object.keys(input)) result[key] = input[key];
  return result;
}''', '''
function dictionary(input) {
  const result = Object.create(null);
  for (const key of Object.keys(input)) result[key] = input[key];
  return result;
}''', "A null-prototype dictionary has no inherited __proto__ setter at this assignment boundary.", "The dictionary is consumed as data and is not subsequently merged into a normal object. This addresses local prototype mutation, not arbitrary downstream consumers.")
pair("1321", "path", "Updating a configuration branch", '''
function setBranch(input, value, config) {
  const parts = input.split('.');
  config[parts[0]][parts[1]] = value;
  return config;
}''', '''
function setBranch(input, value, config) {
  if (input !== 'display.mode') throw new Error('Unknown path');
  config.display.mode = value;
  return config;
}''', "An explicit path avoids traversing inherited prototype objects through attacker-controlled keys.", "config.display is an own trusted plain object and display.mode is the only supported writable field.")

pair("95", "json", "Decoding structured input", '''
function decodeData(input) {
  return eval('(' + input + ')');
}''', '''
function decodeData(input) {
  return JSON.parse(input);
}''', "JSON parsing treats the input as data rather than executable JavaScript.", "Only JSON data is accepted; size limits and schema validation should be applied by the caller.")
pair("95", "formula", "Calculating a supported operation", '''
function calculate(input, a, b) {
  return new Function('a', 'b', 'return ' + input)(a, b);
}''', '''
function calculate(input, a, b) {
  if (input === 'add') return a + b;
  if (input === 'multiply') return a * b;
  throw new Error('Unknown operation');
}''', "Dispatching to fixed operations removes dynamic compilation of input.", "The accepted product operations are add and multiply; operands are validated finite numbers.")
pair("95", "timer", "Scheduling a named action", '''
function schedule(input) {
  return setTimeout(input, 100);
}''', '''
function schedule(input) {
  if (input !== 'refresh') throw new Error('Unknown action');
  return setTimeout(() => location.reload(), 100);
}''', "A fixed callback replaces the browser timer's string-evaluation form.", "This is browser JavaScript; only a refresh action is intended, and input is an untrusted string.")
pair("95", "dispatch", "Dispatching a calculation", '''
function dispatch(input, values) {
  const operation = eval(input);
  return operation(values);
}''', '''
function dispatch(input, values) {
  const operations = {
    sum: items => items.reduce((a, b) => a + b, 0),
    count: items => items.length
  };
  if (!Object.hasOwn(operations, input)) throw new Error('Unknown operation');
  return operations[input](values);
}''', "A fixed own-property dispatch table prevents arbitrary evaluation and inherited-property lookup.", "Only sum and count are supported; values is a validated array of finite numbers.")


def main():
    rows = []
    counts = {}
    for cwe, name, title, before, after, rationale, assumptions in CASES:
        index = counts.get(cwe, 0); counts[cwe] = index+1
        split = ['train', 'train', 'validation', 'test'][index]
        pair_id = f'cwe{cwe}-{name}'
        for label, code in [(1, before), (0, after)]:
            # All authored fixtures use input solely as a local parameter and
            # never access it reflectively, so this rename preserves behaviour.
            view = re.sub(r'\binput\b', 'incomingValue', code)
            rows.append(dict(id=f'{pair_id}-{"vulnerable" if label else "corrected"}', pair_id=pair_id,
                             group_id=pair_id, split=split, label=label, cwe=f'CWE-{cwe}', title=title,
                             code=code, view_code=view, rationale=rationale, assumptions=assumptions,
                             source='authored:patchlens-fixtures-v1', licence='CC0-1.0',
                             review_status='Author-labelled teaching fixture; independent review pending'))
    path=ROOT/'src/patchlens/data/fixtures.jsonl'
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    print(f'Wrote {len(rows)} examples in {len(CASES)} pairs to {path}')


if __name__ == '__main__':
    main()
