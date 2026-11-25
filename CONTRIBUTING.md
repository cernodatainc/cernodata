# Contributing to Cernodata

Thanks for your interest in Cernodata! This guide explains how to start contributing and what we expect from pull requests.

## The most important rule

**No work starts without an issue that a maintainer has accepted and assigned to you.**

This way nobody spends time on a pull request we can't merge, and two people don't work on the same thing. The only exception is a bug you have already fixed (path D below). Outside contributors can't change issue statuses or assign themselves, so you only need to do two things: **comment on the issue** and **manage the state of your PR** (draft / ready for review). The maintainers and automations take care of the rest.

You can follow the status of all tasks in our [project board](https://github.com/orgs/cernodatainc/projects/1).

## How to get started

There are four ways to contribute.

### A. Pick a task from the Backlog

1. Find an open issue with the [`help wanted`](https://github.com/cernodatainc/cernodata/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22+no%3Aassignee) label that nobody is assigned to.
2. Leave a comment saying you'd like to work on it. Add a short plan (2–3 sentences on how you want to do it) and an estimate of how long it will take.
3. Wait until a maintainer assigns the issue to you.
4. Fork the repository and open a **draft** pull request with `Closes #<issue number>` in the description.
5. When the work is done and CI is green, click **Ready for review**.
6. A maintainer reviews and merges your PR. The issue closes automatically.

### B. Report a bug

1. Open a [Bug report](https://github.com/cernodatainc/cernodata/issues/new?template=bug_report.yml).
2. If you want to fix it yourself, check the last box in the form.
3. A maintainer reviews the report. If the bug is confirmed and you offered to fix it, the issue is assigned to you, and you continue from step 4 of path A.

Please don't open a PR before the bug is confirmed. Sometimes what looks like a bug is intended behavior.

### C. Propose a feature

1. Open a [Feature proposal](https://github.com/cernodatainc/cernodata/issues/new?template=feature_proposal.yml). A proposal is a question: "Do you want this in the project?", not ready-made code.
2. The maintainers may ask for more details in the issue.
3. If the proposal is accepted, it goes to the Backlog. Larger features may be split into sub-issues first. If you offered to implement it, it is assigned to you, and you continue from step 4 of path A.
4. If the proposal doesn't fit the project, we close it as *not planned* and explain why.

### D. Submit a bug you have already fixed

If you found a bug and already fixed it for your own use, you can open a pull request right away, without an issue. This applies only to bug fixes. New features always go through path C.

1. Fork the repository and create a branch named `fix/short-description`, e.g. `fix/login-crash`. There is no issue number yet.
2. Open the PR as **Ready for review** right away (CI must be green). In the description, explain what didn't work, how to reproduce it and how you fixed it.
3. A maintainer checks whether it really is a bug and not intended behavior.
4. If it is confirmed, a maintainer reviews and merges your PR.
5. If the change affects intended behavior or doesn't fit the project, we close the PR and explain why.

## Limits

| Contributor | Assigned tasks at a time |
| --- | --- |
| New contributor (no merged PRs yet) | 1 |
| At least 1 merged PR | 2 |

If you don't open a pull request within **14 days** of being assigned, the assignment is removed and the issue goes back to the Backlog.

## Pull request requirements

- Work on a fork, on a branch named `type/number-short-description`, e.g. `fix/42-login-crash` or `feat/57-csv-export`. For a fix without an issue (path D), use `fix/short-description`.
- The PR title follows [Conventional Commits](https://www.conventionalcommits.org/), e.g. `feat: ...`, `fix: ...`, `docs: ...`.
- Check **Allow edits by maintainers**, so we can push small fixes without another review round.
- Fill in the checklist from the PR template.
- Link every issue the PR closes (skip this for path D): add `Closes #<issue number>` to the description, and link the issues in the **Development** section of the PR sidebar (click the gear icon and search by number or title).
- Keep the PR as a draft while you work. Mark it as **Ready for review** only when CI is green. In path D, the work is already done, so you can open it as ready for review right away.

## Communication

Ask questions about a specific issue, bug or proposal in the issue or in your pull request, not in private messages, so the full context stays in the repository.

For everything else, join our Discord. It's where we talk about the project in general, share news and plans, and where you can get to know the team and other contributors.

<!-- Badg Discord -->

<p align="left">
  <a href="https://discord.gg/hXURr32wzG">
    <img src="https://img.shields.io/badge/Join_us_on_Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join us on Discord" height="40">
  </a>
</p>
