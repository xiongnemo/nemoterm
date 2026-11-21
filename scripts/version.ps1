# Works out Nemoterm's version from git: the one implementation of the rules in
# docs/VERSIONING.md, so the build, CI and the release cannot disagree.
#
#   ./scripts/version.ps1      e.g. v0.0.2-main-0123456789ab
#
# It needs a full clone. A shallow one has no tags and gets the v0.0.0
# fallback, which is never published; the source-host job of ci.yml and the
# release check out with fetch-depth: 0 for that reason.
#
# NEMOTERM_BRANCH names the branch, for a run building a commit its own ref
# does not name (the release, which runs after CI on the default branch).
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

# git's own stderr ("No names found") is an answer here, not an error.
function Invoke-Git {
    $ErrorActionPreference = 'Continue'
    $output = & git -C $root @args 2>$null
    [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Out = $output }
}

# --exclude '*-*' keeps out the marker tags the release creates, such as
# v0.0.2-main-0123456789ab: only an exact vMAJOR.MINOR.PATCH tag is a base,
# or each build would count from the previous build instead of the release.
$tag = ''
$described = Invoke-Git describe --tags --abbrev=0 --match 'v[0-9]*' --exclude '*-*' HEAD
if ($described.Ok -and "$($described.Out)" -match '^v(\d+)\.(\d+)\.(\d+)$') {
    $tag = "$($described.Out)"
    $major, $minor, $patch = [int]$Matches[1], [int]$Matches[2], [int]$Matches[3]
}

$head = Invoke-Git rev-parse HEAD
if (!$head.Ok) { throw 'git rev-parse HEAD failed: not a git checkout?' }
$commit = "$($head.Out)".Substring(0, 12)
$status = Invoke-Git status --porcelain
if (!$status.Ok) { throw 'git status failed' }
$dirty = [bool]$status.Out

$commits = 0
if ($tag) {
    $count = Invoke-Git rev-list --count "$tag..HEAD"
    if (!$count.Ok) { throw "git rev-list $tag..HEAD failed" }
    $commits = [int]"$($count.Out)"
}

# A clean build of exactly a tagged commit is that release.
if ($tag -and $commits -eq 0 -and !$dirty) {
    return $tag
}

# GitHub checks out a detached HEAD. On a tag push GITHUB_REF_NAME is the
# tag, which names no branch.
$branch = $env:NEMOTERM_BRANCH
if (!$branch) { $branch = $env:GITHUB_HEAD_REF }
if (!$branch -and $env:GITHUB_REF_TYPE -ne 'tag') { $branch = $env:GITHUB_REF_NAME }
if (!$branch) {
    $abbrev = Invoke-Git rev-parse --abbrev-ref HEAD
    if ($abbrev.Ok) { $branch = "$($abbrev.Out)" }
}
if (!$branch -or $branch -eq 'HEAD') {
    $branch = if ($env:GITHUB_REF_TYPE -eq 'tag') { 'release' } else { 'detached' }
}
# What a version, a tag or a file name cannot carry becomes a dash.
$branch = $branch -replace '[^0-9A-Za-z._-]', '-'

# The patch advances by itself: the tag's plus the commits since it. Before
# the first tag there is no line to count from, and v0.0.0 says so.
$base = if ($tag) { "v$major.$minor.$($patch + $commits)" } else { 'v0.0.0' }
$version = "$base-$branch-$commit"
if ($dirty) { $version += '-dirty' }
$version
