#!/usr/bin/env node

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SKILLS_DIR = path.join(ROOT, 'skills');
const errors = [];

function fail(message) {
  errors.push(message);
}

function readJson(relativePath) {
  try {
    return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'));
  } catch (error) {
    fail(`${relativePath}: ${error.message}`);
    return null;
  }
}

function parseFrontmatter(content) {
  const match = content.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n/);
  if (!match) return null;

  const result = {};
  for (const line of match[1].split(/\r?\n/)) {
    if (/^\s/.test(line)) continue;
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim().replace(/^['"]|['"]$/g, '');
    result[key] = value;
  }
  return result;
}

function validateLocalLinks(skillName, skillFile, content) {
  const skillRoot = path.dirname(skillFile);
  const linkPattern = /\[[^\]]*\]\(([^)]+)\)/g;
  for (const match of content.matchAll(linkPattern)) {
    const target = match[1].trim().replace(/^<|>$/g, '').split('#')[0];
    if (!target || /^(https?:|mailto:|#)/.test(target)) continue;
    const resolved = path.resolve(skillRoot, target);
    if (resolved !== skillRoot && !resolved.startsWith(`${skillRoot}${path.sep}`)) {
      fail(`${skillName}: local reference escapes its skill directory: ${target}`);
    } else if (!fs.existsSync(resolved)) {
      fail(`${skillName}: missing local reference: ${target}`);
    }
  }
}

function validateSkills() {
  if (!fs.existsSync(path.join(ROOT, 'docs', 'skill-anatomy.md'))) {
    fail('docs/skill-anatomy.md: skill contract is missing');
  }
  if (fs.existsSync(path.join(ROOT, 'references'))) {
    fail('repository-root references/ is not allowed; colocate references with each skill');
  }

  const skillNames = fs.readdirSync(SKILLS_DIR)
    .filter((name) => fs.statSync(path.join(SKILLS_DIR, name)).isDirectory())
    .sort();

  for (const skillName of skillNames) {
    const skillFile = path.join(SKILLS_DIR, skillName, 'SKILL.md');
    if (!fs.existsSync(skillFile)) {
      fail(`${skillName}: missing SKILL.md`);
      continue;
    }

    const content = fs.readFileSync(skillFile, 'utf8');
    const frontmatter = parseFrontmatter(content);
    if (!frontmatter) {
      fail(`${skillName}: missing YAML frontmatter`);
      continue;
    }

    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skillName)) {
      fail(`${skillName}: directory must be kebab-case`);
    }
    if (frontmatter.name !== skillName) {
      fail(`${skillName}: frontmatter name must match directory`);
    }
    if (!frontmatter.description) {
      fail(`${skillName}: description is required`);
    } else {
      if (frontmatter.description.length > 1024) fail(`${skillName}: description exceeds 1024 characters`);
      if (!/\buse (?:this )?(?:when|before|after|during)\b/i.test(frontmatter.description)) {
        fail(`${skillName}: description must say when to use the skill`);
      }
    }
    for (const field of ['allowed-tools', 'agent', 'context', 'model']) {
      if (frontmatter[field]) fail(`${skillName}: host-specific frontmatter field \"${field}\" is not portable`);
    }
    if (!/^## Verification\s*$/m.test(content)) {
      fail(`${skillName}: add an evidence-based Verification section`);
    }
    if (!/^## (?:Failure Handling|Handling Failures|Critical Pitfalls)\s*$/m.test(content)) {
      fail(`${skillName}: document failures or critical pitfalls`);
    }

    const hostSpecific = [
      /Claude in Chrome/i,
      /Spawn Task agents?/i,
      /plus Write and Bash/i,
      /\bsubagents?\b/i
    ];
    for (const pattern of hostSpecific) {
      if (pattern.test(content)) fail(`${skillName}: host-specific instruction matches ${pattern}`);
    }

    validateLocalLinks(skillName, skillFile, content);

    const referencesDir = path.join(SKILLS_DIR, skillName, 'references');
    if (fs.existsSync(referencesDir)) {
      for (const referenceName of fs.readdirSync(referencesDir)) {
        const referencePath = path.join(referencesDir, referenceName);
        if (!fs.statSync(referencePath).isFile()) continue;
        if (!content.includes(`references/${referenceName}`)) {
          fail(`${skillName}: reference is not discoverable from SKILL.md: references/${referenceName}`);
        }
      }
    }
  }

  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  for (const skillName of skillNames) {
    if (!readme.includes(`\`${skillName}\``)) fail(`README.md: missing skill ${skillName}`);
  }
}

function validateManifests() {
  const plugin = readJson('.codex-plugin/plugin.json');
  const marketplace = readJson('.agents/plugins/marketplace.json');
  if (!plugin || !marketplace) return;

  if (plugin.name !== path.basename(ROOT)) fail('.codex-plugin/plugin.json: name must match plugin directory');
  if (!/^\d+\.\d+\.\d+$/.test(plugin.version || '')) fail('.codex-plugin/plugin.json: version must be strict semver');
  if (plugin.skills !== './skills/') fail('.codex-plugin/plugin.json: skills must point to ./skills/');
  if (!plugin.author?.name) fail('.codex-plugin/plugin.json: author.name is required');
  for (const field of ['displayName', 'shortDescription', 'longDescription', 'developerName', 'category']) {
    if (!plugin.interface?.[field]) fail(`.codex-plugin/plugin.json: interface.${field} is required`);
  }

  const entry = marketplace.plugins?.find((item) => item.name === plugin.name);
  if (!entry) {
    fail('.agents/plugins/marketplace.json: plugin entry is missing');
    return;
  }
  if (entry.version !== plugin.version) fail('manifest versions must match');
  if (entry.source?.source !== 'local' || entry.source?.path !== './') {
    fail('.agents/plugins/marketplace.json: repo plugin source must be local ./');
  }
  if (!['AVAILABLE', 'INSTALLED_BY_DEFAULT', 'NOT_AVAILABLE'].includes(entry.policy?.installation)) {
    fail('.agents/plugins/marketplace.json: invalid installation policy');
  }
  if (!['ON_INSTALL', 'ON_USE'].includes(entry.policy?.authentication)) {
    fail('.agents/plugins/marketplace.json: invalid authentication policy');
  }
  if (!entry.category) fail('.agents/plugins/marketplace.json: category is required');
}

validateSkills();
validateManifests();

if (errors.length) {
  for (const error of errors) console.error(`ERROR: ${error}`);
  console.error(`\n${errors.length} validation error(s)`);
  process.exit(1);
}

console.log('Repository validation passed.');

module.exports = { parseFrontmatter };
