# Changes from upstream

A fork of `hf-cloud-sagemaker-iam-preflight` from <https://github.com/huggingface/skills>, under its Apache-2.0 licence.

`scripts/check_role.py`, `trust_allows_sagemaker`: the check searched the serialized trust policy for the text
`sagemaker.amazonaws.com`, so these roles passed although SageMaker can't assume them:

- a service such as `sagemaker.amazonaws.com.example.org`;
- a statement with `Effect: Deny`;
- a statement allowing a different action.

It now reads the policy: an `Allow` statement, with `sts:AssumeRole` among its actions, naming exactly that service.
Nothing else is changed.
