#!/usr/bin/env node

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'by', 'for', 'from', 'i', 'in', 'into', 'is', 'it', 'my',
  'of', 'on', 'or', 'our', 'the', 'their', 'these', 'this', 'to', 'use', 'using', 'with'
]);

function tokenize(value) {
  return value.toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .filter((token) => !STOP_WORDS.has(token))
    .map((token) => token
      .replace(/ies$/, 'y')
      .replace(/ing$/, '')
      .replace(/ed$/, '')
      .replace(/s$/, ''));
}

function descriptionFor(skillName) {
  const content = fs.readFileSync(path.join(ROOT, 'skills', skillName, 'SKILL.md'), 'utf8');
  const match = content.match(/^description:\s*["']?(.+?)["']?\s*$/m);
  if (!match) throw new Error(`${skillName}: missing one-line description`);
  return match[1];
}

function score(promptTokens, documentTokens) {
  const counts = new Map();
  for (const token of documentTokens) counts.set(token, (counts.get(token) || 0) + 1);
  return promptTokens.reduce((total, token) => total + Math.min(counts.get(token) || 0, 2), 0);
}

function rank(prompt, skillNames) {
  const promptTokens = tokenize(prompt);
  return skillNames.map((skillName) => ({
    skillName,
    score: score(promptTokens, tokenize(`${skillName} ${descriptionFor(skillName)}`))
  })).sort((a, b) => b.score - a.score || a.skillName.localeCompare(b.skillName));
}

function main() {
  const config = JSON.parse(fs.readFileSync(path.join(ROOT, 'evals', 'routing.json'), 'utf8'));
  const skillNames = fs.readdirSync(path.join(ROOT, 'skills'))
    .filter((name) => fs.statSync(path.join(ROOT, 'skills', name)).isDirectory())
    .sort();
  const failures = [];

  for (const testCase of config.cases) {
    const results = rank(testCase.prompt, skillNames);
    const winner = results[0];
    if (winner.skillName !== testCase.expected || winner.score === 0) {
      failures.push(`${JSON.stringify(testCase.prompt)} expected ${testCase.expected}, got ${winner.skillName} (${winner.score})`);
    }
  }

  if (failures.length) {
    for (const failure of failures) console.error(`FAIL: ${failure}`);
    console.error(`\n${failures.length}/${config.cases.length} routing eval(s) failed.`);
    process.exit(1);
  }

  console.log(`${config.cases.length} routing evals passed.`);
}

if (require.main === module) main();

module.exports = { rank, tokenize };
