import json
import os
import re
import subprocess
import requests
from datetime import datetime, timezone
import sys
import yaml

home = '/home/solv'
config_dir = os.path.expanduser(home + '/.config/solana')
additional_info = 'on'
bin_dir = ''
rpc_url = ''
format_amount = 'SOL'
identity_pubkey = ""
vote_account = ""
validators_data = {}
block_production = {}
epoch_info = {}
log_str = f'nodemonitor'
err_str = ''

def log(key, val):
    global log_str
    global err_str
    if key == 'error':
        val = (val[:75] + '..') if len(val) > 75 else val
        err_str += val + ';'
    else:
        if val is not None:
            log_str = f'{log_str},{key}={val}'

def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        log('error', f"{command} -> {stderr.decode().strip()}")
        return None
    return stdout.decode().strip()

def check_no_voting():
    result = run_command("ps aux | grep solana-validator | grep -c -- '--no-voting'")
    return int(result) == 0 if result else False

def get_identity_pubkey(cli_path):
    try:
        #command = f"{cli_path} address"
        #return run_command(command)
        return get_validator_key(cli_path, config_dir)
    except Exception as e:
        log('error', f'get_identity_pubkey: {e}')
        return None

def get_cli(bin_dir=""):
    try:
        if bin_dir:
            return os.path.join(bin_dir, 'solana')
        with open(os.path.join(config_dir, 'install/config.yml')) as f:
            install_dir = re.search('active_release_dir: (.+)', f.read())
            install_dir = install_dir.group(1) if install_dir else ''
        return os.path.join(install_dir, 'bin', 'solana') if install_dir else ''
    except Exception as e:
        log('error', f'get_cli: {e}')
        return None

def get_rpc_url(cli, rpc_url=None):
    try:
        if rpc_url:
            return rpc_url
        if cli:
            rpc_port = re.search(r'--rpc-port\s+(\d+)', run_command('ps aux | grep solana-validator'))
            rpc_url = f'http://127.0.0.1:{rpc_port.group(1)}' if rpc_port else run_command("solana config get | grep 'RPC URL' | awk '{print $3}'")
        return rpc_url
    except Exception as e:
        log('error', f'get_rpc_url: {e}')
        return "http://127.0.0.1:8899"

def get_validators_data(cli_path, rpc):
    try:
        result = run_command(f"{cli_path} validators --output json")
        return json.loads(result) if result else None
    except Exception as e:
        log('error', f'get_validators_data: {e}')
        return None

def get_solana_price():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT')
        response.raise_for_status()
        price_info = response.json()
        return float(price_info.get('price', 0))
    except (requests.RequestException, ValueError) as e:
        log('error', f'get_solana_price: {e}')
        return None

def get_block_production(cli_path, rpc_url, identity_pubkey):
    try:
        command = f"{cli_path} block-production --output json-compact 2>&- | grep -v Note:"
        block_production = json.loads(run_command(command) or "{}")
        if 'leaders' in block_production:
            for validator in block_production['leaders']:
                if validator.get('identityPubkey') == identity_pubkey:
                    block_production['validator_production'] = validator
                    break
        return block_production
    except Exception as e:
        log('error', f'get_block_production: {e}')
        return None

def version_to_int(version):
    return int(version.replace(".", "")) if version else 0

def get_most_common_version(data):
    stake_by_version = data.get('stakeByVersion', {})
    versions = [{
        "version": key,
        "currentValidators": value['currentValidators'],
        "currentActiveStake": value['currentActiveStake'] // 1000000000,
        "delinquentValidators": value['delinquentValidators']
    } for key, value in stake_by_version.items()]
    return max(versions, key=lambda v: v['currentValidators'])['version'] if versions else None

def get_validator_info(data):
    return next((v for v in data.get('validators', []) if v.get('identityPubkey') == identity_pubkey), None)

def get_epoch_info(cli_path, rpc_url):
    try:
        command = f"{cli_path} epoch-info --url {rpc_url} --output json-compact"
        info = json.loads(run_command(command) or "{}")
        return info
    except Exception as e:
        log('error', f'get_epoch_info: {e}')
        return None

def get_stake_accounts(text):
    try:
        sections = text.strip().split("\n\n")
        stake_accounts = []
        for section in sections:
            stake_account = {}
            for line in section.split("\n"):
                try:
                    if 'undelegated' in line:
                        stake_account['delegated_stake'] = '0'
                        stake_account['active_stake'] = '0'
                    else:
                        key, value = line.split(": ", 1)
                        key = key.lower().replace(' ', '_')
                        value = re.sub('[A-z ]', '', value)
                        stake_account[key] = value
                except Exception as e:
                    log('error', f'get_stake_accounts line: {line} -> {e}')
                    continue
            if 'stake_pubkey' in stake_account:
                stake_accounts.append(
                    f"stake_accounts,stake_pubkey={stake_account['stake_pubkey']},"
                    f"rent_exempt_reserve={stake_account.get('rent_exempt_reserve', '0')},"
                    f"delegated_stake={stake_account.get('delegated_stake', '0')},"
                    f"active_stake={stake_account.get('active_stake', '0')} "
                    f"balance={stake_account.get('balance', '0')}"
                )
        return '\n'.join(stake_accounts)
    except Exception as e:
        log('error', f'get_stake_accounts: {e}')
        return None

def get_validator_key(cli_path, config_dir):
    """
    Retrieves the validator key from the Solana CLI config.yaml file.
    
    Args:
        config_dir (str): Path to the directory containing the Solana config.yaml file.
    
    Returns:
        str: The path to the validator keypair file, or None if not found.
    """
    config_path = os.path.join(config_dir, 'cli/config.yml')
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)  # Use safe_load, as this YAML is straightforward
        
        # Assuming the key is stored under 'validator_keypair' in config.yaml
        validator_key = config_data.get('keypair_path')
        
        if validator_key:
            command = f"{cli_path}-keygen pubkey {validator_key}"
            return run_command(command)
        else:
            log('error', f'get_validator_key: Validator key not found in config file {config_path}')
            return None
    except FileNotFoundError:
        log('error', f'get_validator_key: Config file not found at {config_path}')
        return None
    except yaml.YAMLError as e:
        log('error', f'get_validator_key: Error parsing YAML file {e}')
        return None



if __name__ == "__main__":
    try:
        status = 0
        cli = get_cli(bin_dir)
        rpc = get_rpc_url(cli, rpc_url)
        identity_pubkey = identity_pubkey or get_identity_pubkey(cli) or log('error', 'identityPubkey auto-detection failed') or None
        
        if identity_pubkey:
            log('pubkey', identity_pubkey)
        
        solana_price = get_solana_price() or 0
        log('solanaPrice', solana_price)

        validators_data = get_validators_data(cli, rpc)
        if validators_data:
            validator_info = get_validator_info(validators_data)
            if validator_info:
                epoch_info = get_epoch_info(cli, rpc) or {}
                vote_account = validator_info.get('voteAccountPubkey', '')
                log('activatedStake', "{:.2f}".format(validator_info.get('activatedStake', 0) / 1e9))
                log('commission', validator_info.get('commission', 'N/A'))
                log('credits', validator_info.get('credits', 'N/A'))
                log('lastVote', validator_info.get('lastVote', 'N/A'))
                log('rootSlot', validator_info.get('rootSlot', 'N/A'))
            else:
                log('error', 'No matching validator found')
        else:
            log('error', 'validators_data is empty')

        # Append errors to log_str if any exist
        if err_str:
            err_str = err_str.replace('"', '\\"').replace('\n', ';').replace('\\', '/')
            log_str = f'{log_str},errors="{err_str}"'
        
        # Final log output with timestamp
        current_dt = datetime.now(timezone.utc)
        log_str = f'{log_str} ' + str(int(current_dt.timestamp() * 1e9))
        print(f'{log_str}')
        
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
