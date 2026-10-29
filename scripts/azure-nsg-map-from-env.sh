#!/usr/bin/env bash
# azure-nsg-map-from-env.sh - Map Azure NSGs for hosts listed in a .env file.
#
# Reads PS_HOST_* values from an env file (default: ./.env), resolves hostnames
# to private IPs, and finds matching Azure NICs by private IP. Reports:
# - NIC-level NSG
# - Subnet-level NSG
# - Optional effective NSG payload
#
# Usage:
#   bash scripts/azure-nsg-map-from-env.sh
#   bash scripts/azure-nsg-map-from-env.sh --env-file ./.env --subscription <sub-id>
#   bash scripts/azure-nsg-map-from-env.sh --effective --output json
#
# Requirements:
#   - az CLI logged in
#   - permissions to read NICs/VNETs/NSGs in target subscription(s)

set -euo pipefail

ENV_FILE="${ENV_FILE:-./.env}"
SUBSCRIPTION="${AZ_SUBSCRIPTION_ID:-}"
SHOW_EFFECTIVE=0
OUTPUT_FORMAT="table"

usage() {
  cat <<'EOF'
Usage: azure-nsg-map-from-env.sh [options]

Options:
  --env-file <path>       Path to env file with PS_HOST_* vars (default: ./.env)
  --subscription <id>     Azure subscription ID/name to set before queries
  --effective             Include effective NSG payload for each NIC
  --output <table|json>   Output mode (default: table)
  -h, --help              Show this help

Environment variables:
  ENV_FILE                Same as --env-file
  AZ_SUBSCRIPTION_ID      Same as --subscription

Notes:
- Host discovery uses PS_HOST_01..PS_HOST_99 style variables from env file.
- If a host resolves to multiple IPs, only the first IPv4 address is used.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --subscription)
      SUBSCRIPTION="$2"
      shift 2
      ;;
    --effective)
      SHOW_EFFECTIVE=1
      shift
      ;;
    --output)
      OUTPUT_FORMAT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$OUTPUT_FORMAT" != "table" && "$OUTPUT_FORMAT" != "json" ]]; then
  echo "--output must be one of: table, json" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 2
fi

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI (az) is required." >&2
  exit 2
fi

if ! az account show >/dev/null 2>&1; then
  echo "Azure CLI is not logged in. Run: az login" >&2
  exit 2
fi

if [[ -n "$SUBSCRIPTION" ]]; then
  az account set --subscription "$SUBSCRIPTION"
fi

current_sub="$(az account show --query id -o tsv)"

# shellcheck disable=SC1090
set -a && source "$ENV_FILE" && set +a

discover_hosts() {
  env | awk -F= '/^PS_HOST_[0-9]+=/ {print $1}' | sort | while read -r var_name; do
    host_value="${!var_name:-}"
    if [[ -n "$host_value" ]]; then
      printf '%s\t%s\n' "$var_name" "$host_value"
    fi
  done
}

resolve_ipv4() {
  local host="$1"

  if [[ "$host" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    printf '%s\n' "$host"
    return 0
  fi

  if command -v getent >/dev/null 2>&1; then
    getent hosts "$host" | awk '{print $1}' | grep -E '^[0-9]+\.' | head -n1
    return 0
  fi

  if command -v dig >/dev/null 2>&1; then
    dig +short "$host" A | head -n1
    return 0
  fi

  if command -v host >/dev/null 2>&1; then
    host "$host" | awk '/has address/ {print $NF}' | head -n1
    return 0
  fi

  return 1
}

print_table_header() {
  printf '%-12s %-34s %-16s %-26s %-28s %-28s\n' \
    'HOST_VAR' 'HOST' 'IP' 'NIC' 'NIC_NSG' 'SUBNET_NSG'
}

host_count=0
match_count=0

if [[ "$OUTPUT_FORMAT" == "table" ]]; then
  echo "Azure subscription: $current_sub"
  print_table_header
fi

while IFS=$'\t' read -r host_var host; do
  host_count=$((host_count + 1))
  ip="$(resolve_ipv4 "$host" || true)"

  if [[ -z "$ip" ]]; then
    if [[ "$OUTPUT_FORMAT" == "table" ]]; then
      printf '%-12s %-34s %-16s %-26s %-28s %-28s\n' \
        "$host_var" "$host" 'unresolved' '-' '-' '-'
    else
      printf '{"host_var":"%s","host":"%s","ip":null,"status":"unresolved"}\n' "$host_var" "$host"
    fi
    continue
  fi

  nic_rows="$(az network nic list \
    --query "[?ipConfigurations[?privateIpAddress=='$ip']].{name:name,rg:resourceGroup,nicNsg:networkSecurityGroup.id,subnetId:ipConfigurations[0].subnet.id}" \
    -o tsv)"

  if [[ -z "$nic_rows" ]]; then
    if [[ "$OUTPUT_FORMAT" == "table" ]]; then
      printf '%-12s %-34s %-16s %-26s %-28s %-28s\n' \
        "$host_var" "$host" "$ip" 'not-found' '-' '-'
    else
      printf '{"host_var":"%s","host":"%s","ip":"%s","status":"nic-not-found"}\n' "$host_var" "$host" "$ip"
    fi
    continue
  fi

  while IFS=$'\t' read -r nic_name nic_rg nic_nsg subnet_id; do
    [[ -z "$nic_name" ]] && continue
    match_count=$((match_count + 1))

    subnet_nsg=""
    subnet_rg="$(awk -F/ '{print $5}' <<< "$subnet_id")"
    vnet_name="$(awk -F/ '{print $9}' <<< "$subnet_id")"
    subnet_name="$(awk -F/ '{print $11}' <<< "$subnet_id")"

    if [[ -n "$subnet_rg" && -n "$vnet_name" && -n "$subnet_name" ]]; then
      subnet_nsg="$(az network vnet subnet show \
        --resource-group "$subnet_rg" \
        --vnet-name "$vnet_name" \
        --name "$subnet_name" \
        --query 'networkSecurityGroup.id' -o tsv || true)"
    fi

    short_nic_nsg="${nic_nsg##*/}"
    short_subnet_nsg="${subnet_nsg##*/}"
    [[ -z "$short_nic_nsg" ]] && short_nic_nsg='none'
    [[ -z "$short_subnet_nsg" ]] && short_subnet_nsg='none'

    if [[ "$OUTPUT_FORMAT" == "table" ]]; then
      printf '%-12s %-34s %-16s %-26s %-28s %-28s\n' \
        "$host_var" "$host" "$ip" "$nic_rg/$nic_name" "$short_nic_nsg" "$short_subnet_nsg"
    else
      printf '{"host_var":"%s","host":"%s","ip":"%s","nic":"%s/%s","nic_nsg":"%s","subnet_nsg":"%s"}\n' \
        "$host_var" "$host" "$ip" "$nic_rg" "$nic_name" "$nic_nsg" "$subnet_nsg"
    fi

    if [[ "$SHOW_EFFECTIVE" -eq 1 ]]; then
      if [[ "$OUTPUT_FORMAT" == "table" ]]; then
        echo "  effective_nsg: $nic_rg/$nic_name"
        az network nic list-effective-nsg -g "$nic_rg" -n "$nic_name" -o table || echo "  unable to read effective NSG"
      else
        az network nic list-effective-nsg -g "$nic_rg" -n "$nic_name" -o json || true
      fi
    fi
  done <<< "$nic_rows"
done < <(discover_hosts)

if [[ "$OUTPUT_FORMAT" == "table" ]]; then
  echo ""
  echo "hosts_scanned=$host_count"
  echo "nic_matches=$match_count"
fi
