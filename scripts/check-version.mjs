import fs from 'node:fs';
import { execSync } from 'node:child_process';

/**
 * Parses a semantic version tag (supports both 3-part and 4-part: vMajor.Minor.Patch.Revision)
 * @param {string} tag 
 * @returns {{ major: number, minor: number, patch: number, revision: number } | null}
 */
export function parseVersionTag(tag) {
  if (!tag) return null;
  const cleaned = tag.trim().replace(/^refs\/tags\//, '');
  const match = cleaned.match(/^v?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?$/);
  if (!match) return null;

  return {
    major: parseInt(match[1], 10),
    minor: parseInt(match[2], 10),
    patch: parseInt(match[3] || '0', 10),
    revision: parseInt(match[4] || '0', 10),
  };
}

/**
 * Determines whether a given tag qualifies as Minor or higher version bump.
 * Under mkmv versioning rules:
 * - Major bump: Minor=0, Patch=0, Revision=0
 * - Minor bump: Patch=0, Revision=0
 * - Patch bump: Patch > 0
 * - Revision bump: Revision > 0
 * 
 * @param {string} currentTag 
 * @param {string[]} [allTags=[]]
 * @returns {{ shouldBuild: boolean, reason: string, current: object | null }}
 */
export function evaluateVersionBump(currentTag, allTags = []) {
  const current = parseVersionTag(currentTag);
  if (!current) {
    return {
      shouldBuild: false,
      reason: `Tag "${currentTag}" is not a valid semantic version format (e.g. v0.1.0.0 or v1.0.0).`,
      current: null
    };
  }

  // 1. In mkmv 4-part rules, Minor/Major bump guarantees patch=0 and revision=0
  if (current.patch > 0 || current.revision > 0) {
    return {
      shouldBuild: false,
      reason: `Tag is a patch/revision release (patch=${current.patch}, revision=${current.revision}). Minor or higher is required.`,
      current
    };
  }

  // 2. If historical tags exist, compare against previous tags
  const validPreviousTags = allTags
    .map(t => ({ raw: t, ver: parseVersionTag(t) }))
    .filter(item => item.ver !== null && item.raw !== currentTag)
    .sort((a, b) => {
      if (a.ver.major !== b.ver.major) return b.ver.major - a.ver.major;
      if (a.ver.minor !== b.ver.minor) return b.ver.minor - a.ver.minor;
      if (a.ver.patch !== b.ver.patch) return b.ver.patch - a.ver.patch;
      return b.ver.revision - a.ver.revision;
    });

  if (validPreviousTags.length > 0) {
    const prev = validPreviousTags[0].ver;
    const isHigherMinorOrMajor =
      (current.major > prev.major) ||
      (current.major === prev.major && current.minor > prev.minor);

    if (!isHigherMinorOrMajor) {
      return {
        shouldBuild: false,
        reason: `Current tag (v${current.major}.${current.minor}.${current.patch}.${current.revision}) is not higher in Minor/Major than previous tag (${validPreviousTags[0].raw}).`,
        current
      };
    }
  }

  return {
    shouldBuild: true,
    reason: `Tag satisfies Minor or higher version bump (Major=${current.major}, Minor=${current.minor}, Patch=0, Revision=0).`,
    current
  };
}

// CLI Execution entry point
if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'))) {
  const tagArg = process.argv[2] || process.env.TAG_NAME || process.env.GITHUB_REF_NAME || '';
  
  let gitTags = [];
  try {
    const stdout = execSync('git tag -l', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    gitTags = stdout.split('\n').map(s => s.trim()).filter(Boolean);
  } catch {
    // Git might not have tags or git command not available
  }

  console.log(`[check-version] Evaluating tag: "${tagArg}"`);
  const result = evaluateVersionBump(tagArg, gitTags);

  console.log(`[check-version] Result: ${result.shouldBuild ? '✅ ALLOW' : '⏭️ SKIP'}`);
  console.log(`[check-version] Reason: ${result.reason}`);

  const githubOutput = process.env.GITHUB_OUTPUT;
  if (githubOutput) {
    fs.appendFileSync(githubOutput, `should_build=${result.shouldBuild}\n`);
    console.log(`[check-version] Written should_build=${result.shouldBuild} to $GITHUB_OUTPUT`);
  }
}
