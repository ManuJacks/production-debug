#!/usr/bin/env bash
# nsg-egress-validate.sh - Validate Jenkins NSG egress posture without endpoint probing.
#
# Method A: Azure Network Watcher IP flow decision simulation per host.
# Method B: Optional NSG flow-log corroboration from Log Analytics.

set -euo pipefail

ENV_FILE="${ENV_FILE:-./.env}"
SUBSCRIPTION="${AZ_SUBSCRIPTION_ID:-}"
WORKSPACE_ID="${LAW_WORKSPACE_ID:-}"
TEST_IP="${TEST_IP:-198.51.100.10}"
TEST_PORT="${TEST_PORT:-443}"
LOCAL_PORT="${LOCAL_PORT:-40000}"
TIMESPAN="${TIMESPAN:-PT24H}"
OUTPUT_FORMAT="table"
RUN_FLOWLOG=0

usage() {
	cat <<'EOF'
Usage: nsg-egress-validate.sh [options]

Options:
	--env-file <path>          Path to env file with PS_HOST_* vars (default: ./.env)
	--subscription <id>        Azure subscription ID/name override
	--test-ip <ipv4>           Remote IPv4 for simulation (default: 198.51.100.10)
	--test-port <port>         Remote TCP port for simulation (default: 443)
	--local-port <port>        Local source port for simulation (default: 40000)
	--workspace <id>           Log Analytics workspace ID for Method B
	--timespan <PT24H>         Log Analytics timespan (default: PT24H)
	--flow-logs                Run Method B (requires --workspace)
	--output <table|json>      Output mode (default: table)
	-h, --help                 Show this help

Environment variables:
	ENV_FILE, AZ_SUBSCRIPTION_ID, LAW_WORKSPACE_ID
	TEST_IP, TEST_PORT, LOCAL_PORT, TIMESPAN

Examples:
	bash scripts/nsg-egress-validate.sh
	bash scripts/nsg-egress-validate.sh --subscription <sub-id>
	bash scripts/nsg-egress-validate.sh --flow-logs --workspace <law-id> --timespan PT48H
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
		--test-ip)
			TEST_IP="$2"
			shift 2
			;;
		--test-port)
			TEST_PORT="$2"
			shift 2
			;;
		--local-port)
			LOCAL_PORT="$2"
			shift 2
			;;
		--workspace)
			WORKSPACE_ID="$2"
			shift 2
			;;
		--timespan)
			TIMESPAN="$2"
			shift 2
			;;
		--flow-logs)
			RUN_FLOWLOG=1
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

if [[ "$RUN_FLOWLOG" -eq 1 && -z "$WORKSPACE_ID" ]]; then
	echo "--flow-logs requires --workspace <law-workspace-id>" >&2
	exit 2
fi

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

find_vm_by_ip() {
	local ip="$1"
	az vm list -d \
		--query "[?contains(privateIps, '$ip')].[name,resourceGroup]" \
		-o tsv | head -n1
}

list_nsgs_for_ip() {
	local ip="$1"
	local nic_rows
	local nic_nsg
	local subnet_id
	local subnet_rg
	local vnet_name
	local subnet_name
	local subnet_nsg

	nic_rows="$(az network nic list \
		--query "[?ipConfigurations[?privateIpAddress=='$ip']].{nicNsg:networkSecurityGroup.id,subnetId:ipConfigurations[0].subnet.id}" \
		-o tsv || true)"

	while IFS=$'\t' read -r nic_nsg subnet_id; do
		[[ -n "$nic_nsg" ]] && printf '%s\n' "${nic_nsg##*/}"

		if [[ -n "$subnet_id" ]]; then
			subnet_rg="$(awk -F/ '{print $5}' <<< "$subnet_id")"
			vnet_name="$(awk -F/ '{print $9}' <<< "$subnet_id")"
			subnet_name="$(awk -F/ '{print $11}' <<< "$subnet_id")"
			if [[ -n "$subnet_rg" && -n "$vnet_name" && -n "$subnet_name" ]]; then
				subnet_nsg="$(az network vnet subnet show \
					--resource-group "$subnet_rg" \
					--vnet-name "$vnet_name" \
					--name "$subnet_name" \
					--query 'networkSecurityGroup.id' -o tsv || true)"
				[[ -n "$subnet_nsg" ]] && printf '%s\n' "${subnet_nsg##*/}"
			fi
		fi
	done <<< "$nic_rows"
}

if [[ "$OUTPUT_FORMAT" == "table" ]]; then
	echo "Method A: IP Flow Verify simulation"
	printf '%-12s %-34s %-15s %-26s %-7s %-48s\n' \
		'HOST_VAR' 'HOST' 'IP' 'VM' 'ACCESS' 'RULE'
fi

nsg_tmp_file="$(mktemp)"
trap 'rm -f "$nsg_tmp_file"' EXIT

host_count=0
allow_count=0
deny_count=0
error_count=0

while IFS=$'\t' read -r host_var host; do
	host_count=$((host_count + 1))
	ip="$(resolve_ipv4 "$host" || true)"

	if [[ -z "$ip" ]]; then
		error_count=$((error_count + 1))
		if [[ "$OUTPUT_FORMAT" == "table" ]]; then
			printf '%-12s %-34s %-15s %-26s %-7s %-48s\n' \
				"$host_var" "$host" 'unresolved' '-' 'ERROR' 'host-ip-unresolved'
		else
			printf '{"host_var":"%s","host":"%s","ip":null,"access":"ERROR","rule":"host-ip-unresolved"}\n' "$host_var" "$host"
		fi
		continue
	fi

	vm_row="$(find_vm_by_ip "$ip" || true)"
	vm_name="$(awk '{print $1}' <<< "$vm_row")"
	vm_rg="$(awk '{print $2}' <<< "$vm_row")"

	if [[ -z "$vm_name" || -z "$vm_rg" ]]; then
		error_count=$((error_count + 1))
		if [[ "$OUTPUT_FORMAT" == "table" ]]; then
			printf '%-12s %-34s %-15s %-26s %-7s %-48s\n' \
				"$host_var" "$host" "$ip" '-' 'ERROR' 'vm-not-found-for-ip'
		else
			printf '{"host_var":"%s","host":"%s","ip":"%s","access":"ERROR","rule":"vm-not-found-for-ip"}\n' "$host_var" "$host" "$ip"
		fi
		continue
	fi

	access="$(az network watcher test-ip-flow \
		--resource-group "$vm_rg" \
		--vm "$vm_name" \
		--direction Outbound \
		--protocol TCP \
		--local "$ip:$LOCAL_PORT" \
		--remote "$TEST_IP:$TEST_PORT" \
		--query 'access' \
		-o tsv 2>/dev/null || true)"

	rule_name="$(az network watcher test-ip-flow \
		--resource-group "$vm_rg" \
		--vm "$vm_name" \
		--direction Outbound \
		--protocol TCP \
		--local "$ip:$LOCAL_PORT" \
		--remote "$TEST_IP:$TEST_PORT" \
		--query 'ruleName' \
		-o tsv 2>/dev/null | head -n1 || true)"

	if [[ -z "$access" ]]; then
		access='ERROR'
		rule_name='test-ip-flow-failed'
		error_count=$((error_count + 1))
	else
		rule_name="$(echo "$rule_name" | head -n1)"
		[[ -z "$rule_name" ]] && rule_name='(no-rule-returned)'
		if [[ "$access" == "Allow" ]]; then
			allow_count=$((allow_count + 1))
		elif [[ "$access" == "Deny" ]]; then
			deny_count=$((deny_count + 1))
		fi
	fi

	while IFS= read -r nsg_name; do
		[[ -z "$nsg_name" ]] && continue
		echo "$nsg_name" >> "$nsg_tmp_file"
	done < <(list_nsgs_for_ip "$ip")

	if [[ "$OUTPUT_FORMAT" == "table" ]]; then
		printf '%-12s %-34s %-15s %-26s %-7s %-48s\n' \
			"$host_var" "$host" "$ip" "$vm_name" "$access" "$rule_name"
	else
		printf '{"host_var":"%s","host":"%s","ip":"%s","vm":"%s","access":"%s","rule":"%s"}\n' \
			"$host_var" "$host" "$ip" "$vm_name" "$access" "$rule_name"
	fi
done < <(discover_hosts)

if [[ "$OUTPUT_FORMAT" == "table" ]]; then
	echo ""
	echo "method_a_hosts_scanned=$host_count"
	echo "method_a_allow_count=$allow_count"
	echo "method_a_deny_count=$deny_count"
	echo "method_a_error_count=$error_count"
fi

if [[ "$RUN_FLOWLOG" -eq 1 ]]; then
	mapfile_nsg() {
		sort -u "$nsg_tmp_file"
	}

	nsg_csv=""
	while IFS= read -r nsg_name; do
		[[ -z "$nsg_name" ]] && continue
		if [[ -z "$nsg_csv" ]]; then
			nsg_csv="'$nsg_name'"
		else
			nsg_csv="$nsg_csv,'$nsg_name'"
		fi
	done < <(mapfile_nsg)

	if [[ -z "$nsg_csv" ]]; then
		echo "Method B skipped: no NSGs discovered from hosts." >&2
		exit 0
	fi

	echo ""
	echo "Method B: NSG flow-log corroboration"

	read -r -d '' analytics_query <<EOF || true
AzureNetworkAnalytics_CL
| where SubType_s == 'FlowLog'
| where NSG_s in ($nsg_csv)
| where FlowDirection_s == 'O'
| where FlowStatus_s == 'A'
| summarize count() by NSG_s, DestIP_s, DestPort_d, bin(TimeGenerated, 1h)
| order by TimeGenerated desc
EOF

	az monitor log-analytics query \
		--workspace "$WORKSPACE_ID" \
		--timespan "$TIMESPAN" \
		--analytics-query "$analytics_query" \
		-o "$OUTPUT_FORMAT"
fi
