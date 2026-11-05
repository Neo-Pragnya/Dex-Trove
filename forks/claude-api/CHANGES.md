# Changes from upstream

A fork of `claude-api` from <https://github.com/anthropics/skills>, under its Apache-2.0 licence.

`shared/preserved-thinking-migration/drop_block_probe.py`: two messages printed the list of beta headers, which is built partly from what the credentials are. They now print only the betas you asked for on the command line, so nothing derived from credentials reaches the output.

Nothing else is changed.
