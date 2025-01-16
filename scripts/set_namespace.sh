#!/usr/bin/env bash

namespace=$1

kubectl config set-context --current --namespace=${namespace}