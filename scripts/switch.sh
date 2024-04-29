#!/bin/sh
if [ -n "$1" ]; then
	echo "turn off"
	from_ip=$(hostname -I | awk '{print $1}')
	from_port=$(grep -i '^Port ' /etc/ssh/sshd_config | awk '{print $2}')
	to_ip=$1
	to_port=$2
	echo "from $from_ip:$from_port"
	echo "to $to_ip:$to_port"
	solana-validator -l %validator_ledger% wait-for-restart-window --min-idle-time 2 --skip-new-snapshot-check
	solana-validator -l %validator_ledger% set-identity %solana_keypath%/unstaked-identity.json
	ln -sf %solana_keypath%/unstaked-identity.json %solana_keypath%/identity.json
	
	scp -i %solana_keypath%/open_ppk.txt -P $to_port /etc/telegraf/telegraf.conf root@$to_ip:/etc/telegraf
	scp -i %solana_keypath%/open_ppk.txt -P $to_port /etc/systemd/system/solana.service root@$to_ip:/etc/systemd/system
	
	scp -i %solana_keypath%/open_ppk.txt -P $to_port %validator_ledger%/tower-1_9-$(solana-keygen pubkey %solana_keypath%/validator-keypair.json).bin root@$to_ip:%validator_ledger%
	scp -i %solana_keypath%/open_ppk.txt -P $to_port %solana_keypath%/scripts/switch.sh root@$to_ip:%solana_keypath%/scripts/
	ssh -i %solana_keypath%/open_ppk.txt root@$to_ip -p $to_port 'cd %solana_keypath%/scripts/ && chmod +x switch.sh && ./switch.sh'
	systemctl stop telegraf
else 
	echo "turn on";
	export PATH="/root/.local/share/solana/install/active_release/bin:$PATH"
	solana-validator -l %solana_keypath%/validator-ledger set-identity --require-tower %solana_keypath%/validator-keypair.json
	ln -sf %solana_keypath%/validator-keypair.json %solana_keypath%/identity.json
	systemctl daemon-reload
	systemctl restart telegraf
fi
