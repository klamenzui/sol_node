import json
import os
import re
import subprocess
import requests
from datetime import datetime, timezone
import sys
import yaml

# Configuration variables
# home = '/home/solv'
home = '/root'
config_dir = os.path.expanduser(home + '/.config/solana')
additional_info = 'on'
bin_dir = ''
rpc_url = ''
format_amount = 'SOL'
identity_pubkey = ""  # Initial leer, wird bei Bedarf festgelegt
vote_account = ""  # Initial leer, wird bei Bedarf festgelegt
validators_data = {}
block_production = {}
epoch_info = {}
log_str=f'nodemonitor'
err_str=''

def log(key, val):
    global log_str
    global err_str
    #print(key, val)
    if key == 'error':
        val = re.sub(r'^/[^ ]+', '..', val)
        val = (val[:75] + '..') if len(val) > 75 else val
        err_str += val + ';'
    else:
        if not (val is None):
            log_str=f'{log_str},{key}={val}'

# Helper function to run Solana CLI commands
def run_command(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        log('error', f"{command} -> {stderr.decode().strip()}")
        return None
    return stdout.decode().strip()

def check_no_voting():
    """Prüft, ob der Validator mit der Option --no-voting läuft."""
    command = "ps aux | grep agave-validator | grep -c -- '--no-voting'"
    result = run_command(command)
    return int(result) == 0

def get_identity_pubkey(cli_path):
    try:
        #command = f"{cli_path} address  --url {rpc_url}"
        #return run_command(command)
        return get_validator_key(cli_path, config_dir)
    except Exception as e:
        log('error', f'get_identity_pubkey: {e}')
        return None

def get_cli(bin_dir = ""):
    # Detect Solana binary directory
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
        #return "http://127.0.0.1:8899"
        return ''
        
# Beispiel für das Abfragen des Validator-Status
def get_validators_data(cli_path, rpc=''):
    try:
        res = run_command(f"{cli_path} validators {rpc} --output json")
        return json.loads(res) if res else None
    except Exception as e:
        #print(e)
        log('error', f'get_validators_data: {e}')
        return None

# Beispiel für das Abrufen des Solana-Preises
def get_solana_price():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT')
        response.raise_for_status()
        price_info = response.json()
        return float(price_info.get('price', 0))
    except (requests.RequestException, ValueError) as e:
        log('error', f'get_solana_price: {e}')
        return None
    
# block_production=$($cli block-production --url $rpcURL --output json-compact 2>&- | grep -v Note:)
# validatorBlockProduction=$(jq -r '.leaders[] | select(.identityPubkey == '\"$identityPubkey\"')' <<<$blockProduction)
def get_block_production(cli_path, rpc_url, identity_pubkey):
    try:
        """Ruft das Vote-Account des Validators ab."""
        command = f"{cli_path} block-production {rpc_url} --output json-compact 2>&- | grep -v Note:"
        block_production = json.loads(run_command(command) or "{}")
        if 'leaders' in block_production:
            for validator in block_production['leaders']:
                if validator.get('identityPubkey') == identity_pubkey:
                    block_production['validator_production'] = validator
                    return block_production
        return block_production
    except Exception as e:
        #print(e)
        log('error', f'get_block_production: {e}')
        return None

    
# Umwandlung der Versionsstrings in vergleichbare Zahlen
def version_to_int(version):
    return int(version.replace(".", "")) if version else 0
    
def get_most_common_version(data):
    # Verarbeiten der Daten, um stakeByVersion zu extrahieren
    stake_by_version = data.get('stakeByVersion', {})
    versions = [{
        "version": key,
        "currentValidators": value['currentValidators'],
        "currentActiveStake": value['currentActiveStake'] // 1000000000,  # Umrechnung von Lamports in SOL und Abrunden
        "delinquentValidators": value['delinquentValidators']
    } for key, value in stake_by_version.items()]

    # Bestimmen der am weitesten verbreiteten Version
    most_common_version = max(versions, key=lambda v: v['currentValidators'])['version'] if versions else None
    return most_common_version
    
def get_validator_info(data):
    return next((v for v in data.get('validators', []) if v.get('identityPubkey') == identity_pubkey), None)
    
def get_epoch_info(cli_path, rpc_url):
    try:
        command = f"{cli_path} epoch-info {rpc_url} --output json-compact"
        info = json.loads(run_command(command) or "{}")
        return info
    except Exception as e:
        #print(e)
        log('error', f'get_epoch_info: {e}')
        return None
    
    
def get_stake_accounts(text):
    try:
        # Split the text into sections for each stake account
        sections = text.strip().split("\n\n")

        # Initialize a list to hold dictionaries
        stake_accounts = []

        # Loop through each section to parse it
        for section in sections:
            # Split the section into lines
            lines = section.split("\n")
            stake_account = {}
            # Loop through each line in the section
            for line in lines:
                try:
                    # Split the line into key and value
                    if 'undelegated' in line:
                        stake_account['delegated_stake'] = '0'
                        stake_account['active_stake'] = '0'
                    else:
                        key, value = line.split(": ", 1)
                        key = key.lower().replace(' ', '_')
                        #if key in ('stake_pubkey','balance','rent_exempt_reserve','delegated_stake','active_stake'):
                        if key != 'stake_pubkey':
                            value = re.sub('[A-z ]', '', value)
                        stake_account[key] = value
                except Exception as e:
                    #print(line, e)
                    log('error', f'get_stake_accounts line: {line} -> {e}')
                    pass
            # Add the dictionary to the list
            if 'stake_pubkey' in stake_account:
                stake_accounts.append(
                    f"stake_accounts,stake_pubkey={stake_account['stake_pubkey']},"
                    f"rent_exempt_reserve={stake_account.get('rent_exempt_reserve', '0')},"
                    f"delegated_stake={stake_account.get('delegated_stake', '0')},"
                    f"active_stake={stake_account.get('active_stake', '0')} "
                    f"balance={stake_account.get('balance', '0')}"
                )
        # stake_accounts now contains an array of dictionaries with the parsed data
        #print(stake_accounts)
        return '\n'.join(stake_accounts)
    except Exception as e:
        #print(e)
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
        #print(run_command(f'{cli} catchup ~/solana/validator-keypair.json {rpc}'))
        #status 0=validating 1=up 2=error 3=delinquent 4=stopped
        status = 0
        #cli_path = bin_dir if bin_dir else "solana"  # Ersetzen Sie dies durch den tatsächlichen Pfad zu Ihrem Solana-CLI-Tool
        cli = get_cli(bin_dir)
        rpc = '' #get_rpc_url(cli, rpc_url)
        if rpc:
            rpc = f'--url {rpc}'
        if not identity_pubkey:
            identity_pubkey = get_identity_pubkey(cli)
            if not identity_pubkey:
                #raise Exception("Auto-detection failed, please configure the identityPubkey in the script if not done")
                status=4
                log('error', 'identityPubkey auto-detection failed')
                #return None
        
        stake_accounts = ''
        log('pubkey', identity_pubkey)
        solana_price = get_solana_price()
        #log('solanaPrice', get_solana_price())
        log_str=f'{log_str} solanaPrice={solana_price}'
            
        validators_data = get_validators_data(cli, rpc)
        if validators_data:
            validator_info = get_validator_info(validators_data)
            epoch_info = get_epoch_info(cli, rpc)
            vote_account = validator_info.get('voteAccountPubkey', '')
            activated_stake = "{:.2f}".format(validator_info['activatedStake'] / 1000000000.0)#sol
            log('activatedStake', activated_stake)
            log('commission', validator_info.get('commission', 'N/A'))
            log('credits', validator_info.get('credits', 'N/A'))
            log('lastVote', validator_info.get('lastVote', 'N/A'))
            log('rootSlot', validator_info.get('rootSlot', 'N/A'))
            log('version', '"' + validator_info.get('version', 'N/A') + '"')
            most_common_version = get_most_common_version(validators_data)
            log('remoteVersion', '"' + most_common_version + '"')
            most_common_version_int = version_to_int(most_common_version)
            current_version_int = version_to_int(validator_info.get('version', '0'))
            # Entscheiden, ob ein Update erforderlich ist
            update_version = 0 if current_version_int >= most_common_version_int else 1
            log('updateVersion', update_version)
            stake_accounts = get_stake_accounts(run_command(f'{cli} stakes {vote_account}'))
            if stake_accounts is None:
                stake_accounts = ''
            else:
                stake_accounts = f'\n{stake_accounts}'
            log('validatorCreditsCurrent', run_command(f'{cli} vote-account {vote_account} | grep credits/slots | cut -d ":" -f 2 | cut -d "/" -f 1 | ' + "awk 'NR==1{print $1}'"))
            log('validatorVoteBalance', run_command(f'{cli} balance {vote_account} | grep -o "[0-9.]*"'))
            log('epoch', epoch_info['epoch'])
            #log('pctEpochElapsed', "{:.2f}".format(100 * epoch_info['slotIndex'] / epoch_info['slotsInEpoch']))
            log('pctEpochElapsed', epoch_info['epochCompletedPercent'])
        else:
            status = 4
            log('error', 'validators_data is empty')
        if identity_pubkey:
            log('validatorBalance', run_command(f'{cli} balance {identity_pubkey} | grep -o "[0-9.]*"'))
            block_production = get_block_production(cli, rpc, identity_pubkey)
            if block_production:
                # Direktes Extrahieren von Werten aus dem JSON
                total_blocks_produced = block_production['total_slots']
                total_slots_skipped = block_production['total_slots_skipped']
                validator_production = {
                    "blocksProduced":0,
                    "leaderSlots":0,
                    "skippedSlots":0
                }
                if 'validator_production' in block_production:
                    validator_production = block_production['validator_production']
                # Berechnungen
                pct_skipped=0
                pct_skipped_delta=0
                if validator_production['leaderSlots'] > 0:
                    pct_skipped=round(100 * validator_production['skippedSlots'] / validator_production['leaderSlots'], 2)
                if total_blocks_produced > 0:
                    pct_tot_skipped = round((total_slots_skipped / total_blocks_produced) * 100, 2)
                    pct_skipped_delta=round(100 * (pct_skipped - pct_tot_skipped) / pct_tot_skipped, 2)
                else:
                    pct_tot_skipped = 0

                total_active_stake = validators_data['totalActiveStake']
                total_delinquent_stake = validators_data['totalDelinquentStake']
                pct_tot_delinquent = (total_delinquent_stake / total_active_stake) * 100 if total_active_stake > 0 else 0

                # Annahme: 'version' und 'activatedStake' sind bekannt und definiert
                version = validator_info['version']
                # Weitere Berechnungen
                stake_by_version = validators_data['stakeByVersion']
                version_active_stake = stake_by_version[version]['currentActiveStake'] if version in stake_by_version else 0

                # Berechnung des prozentualen Anteils der aktiven Stake der Version im Vergleich zur gesamten aktuellen Stake
                pct_version_active = (version_active_stake / total_active_stake) * 100 if total_active_stake > 0 else 0

                # Berechnung des prozentualen Anteils neuerer Versionen
                # Hierfür muss eine Logik implementiert werden, um 'stakeNewerVersions' zu bestimmen
                # Dies kann komplex werden, je nachdem, wie Sie "neuere" Versionen definieren. Eine einfache Annäherung:
                stake_newer_versions = sum(value['currentActiveStake'] for key, value in stake_by_version.items() if key > version)
                pct_newer_versions = (stake_newer_versions / total_active_stake) * 100 if total_active_stake > 0 else 0

                log('pctSkipped', pct_skipped)
                
                #print(f"Total Blocks Produced: {total_blocks_produced}")
                #log('totalBlocksProduced', total_blocks_produced)
                #print(f"Total Slots Skipped: {total_slots_skipped}")
                #print(f"Percentage of Total Slots Skipped: {pct_tot_skipped}")
                log('pctTotSkipped', pct_tot_skipped)
                log('pctSkippedDelta', pct_skipped_delta)
                #print(f"Percentage of Total Delinquent Stake: {pct_tot_delinquent}")
                log('pctTotDelinquent', pct_tot_delinquent)
                #print(f"Activated Stake in SOL: {activated_stake}")
                log('activatedStake', activated_stake)
                #print(f"Percentage of Version Active Stake: {pct_version_active}")
                log('pctVersionActive', pct_version_active)
                #print(f"Percentage of Newer Versions Stake: {pct_newer_versions}")
                log('pctNewerVersions', pct_newer_versions)
                log('blocksProduced', validator_production['blocksProduced'])
                log('skippedSlots', validator_production['skippedSlots'])
                log('leaderSlots', validator_production['leaderSlots'])
                #print(block_production)
            else:
                status = 4
                log('error', 'block_production is empty')
        
        log('openFiles', run_command("cat /proc/sys/fs/file-nr | awk '{ print $1 }'"))
        log('nodes', run_command(f'{cli} gossip {rpc} | grep -Po "Nodes:\s+\K[0-9]+"'))
        if err_str != '':
            err_str = err_str.replace('"', '\\"').replace('\n', ';').replace('\\', '/')
            log_str = f'{log_str},errors="{err_str}"'
        log('status', status)
        current_dt = datetime.now(timezone.utc)
        log_str = f'{log_str} ' + str(int(current_dt.timestamp() * 1e9))
        print(f'{log_str}{stake_accounts}')
    except Exception as e:
        print(e)
