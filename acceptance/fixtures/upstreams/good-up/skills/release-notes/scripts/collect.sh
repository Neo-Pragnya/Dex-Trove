#!/usr/bin/env bash
git log --merges --oneline "$1"..HEAD
