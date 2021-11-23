solana public registry =	https://docs.google.com/spreadsheets/d/1pEdQoSxBakwsaHuGgiQVoYcu49WWbZfhOus_H5ZyDL4/edit#gid=0
telegram token  =			%telegram_token%
//mb || tds
solana app =				mb
//solana rpc =				https://api.mainnet-beta.solana.com/
//solana rpc =				localhost
chat access username =		%chat_access%
bot certificate =			ssl/my.pem
//absolute path
solana key path =			%solana_keypath%
watch interval min =		1
//cmd list -> full name from cmd_abbr = cmd. %key_from_settings.v% will replace
key validator =				solana-keygen pubkey %solana_key_path%validator-keypair.json
key vote =					solana-keygen pubkey %solana_key_path%vote-account-keypair.json
balance =					echo "validator:" && solana balance %key_validator% && echo "vote:" && solana balance %key_vote%
install %param% =			solana-install init %param% && systemctl daemon-reload && service solana restart
configuration =				cat /etc/systemd/system/solana.service
catchup =					timeout 30 solana catchup %key_validator%
delinquent =				solana validators --output json | jq .delinquentValidators[].identityPubkey -r | grep %key_validator% | echo ";"
version =					solana --version
//stakes validator =			solana stakes %key_validator%
stakes vote =				solana stakes %key_vote%
production =				solana block-production --epoch $(solana epoch ) | grep -e "Identity\|%key_validator%"
withdraw %param% =			solana withdraw-from-vote-account %solana_key_path%vote-account-keypair.json %solana_key_path%validator-keypair.json %param% --authorized-withdrawer %solana_key_path%authority-keypair.json
transfer %param% =			solana transfer -k %solana_key_path%validator-keypair.json 5o9AZteUreaQZ2K7ycXdmE7fQF58ZnM9bye6jtAHPzjS %param%
