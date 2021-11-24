#!/usr/bin/env node
const TelegramBot = require ( 'node-telegram-bot-api');
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const netData = {};
var messages = {};
var bot = {};
var cmd_arr = [];
const rootDir = __dirname;
const settings = {
	ip: null,
	sol_ident_key: null,
	watch_interval_min: null,
	telegram_token: null,
	bot:{
		chat_id: null,
		options: {
			certificate: null,
			polling: true
		}
	}
};
const watcher = {
	chatId: null,
	run: false,
	tasks:[{
			cmd: 'catchup',
			expected:'[0-9A-z\s]+ has caught up [0-9A-z\(\):\s]+'
		},{
			cmd: 'delinquent',
			expected:'^\\s*;'
		}
	],
	taskIndex: 0,
	task: function(params){
		if(params && params.length > 0){
			watcher.chatId = settings.bot.chat_id;
			switch(params[0]){
				case "start": 
					message('me0', os.hostname());
					settings.watch_interval_min = parseInt(settings.watch_interval_min);
					message('me1', settings.watch_interval_min);
					watcher.run = true;
					watcher.waitAndDo();
					bot.sendMessage(watcher.chatId, message('me2'));
				break;
				case "stop":
					watcher.run = false;
					bot.sendMessage(watcher.chatId, message('md0'));
				break;
				case "status":
					bot.sendMessage(watcher.chatId, message('ms0',(!watcher.run?'disabled':'enabled')));
				break;
				case "interval":
					settings.watch_interval_min = parseInt(params[2])
					bot.sendMessage(watcher.chatId, message('mi0', params[1]));
				break;
			}
		} else {
			message('shc',settings.solana_app, 'monitoring');
		}
	},
	waitAndDo: function() {
		if(!watcher.run) {
			bot.sendMessage(watcher.chatId, message('md1'));
			return;
		}
		setTimeout(function() {
			let stdout = cmdExec(watcher.tasks[watcher.taskIndex].cmd);
			if(stdout.toLowerCase().indexOf("error") > -1){
				message('mr0', stdout);
			} else {
				let regExp = new RegExp(watcher.tasks[watcher.taskIndex].expected, "g");
				message('mr1',watcher.taskIndex,watcher.tasks[watcher.taskIndex].cmd, regExp,stdout);
				if(stdout.match(regExp)!= null){
					message('mr3');
				} else {
					message('mr2');
					bot.sendMessage(watcher.chatId, message('mr4',watcher.tasks[watcher.taskIndex].cmd, os.hostname(),stdout));
				}
			}
			if(watcher.taskIndex + 1 >= watcher.tasks.length){
				watcher.taskIndex = 0;
			} else {
				watcher.taskIndex++;
			}
			watcher.waitAndDo();
		}, (60000 * settings.watch_interval_min));
	}
};
function message(){
	var res = "" + messages[arguments[0]];
	for(var i = 1; i<arguments.length; i++){
		res = res.replace('%', "" + arguments[i]);//.replace(new RegExp('(:?root)','g'), "<your user>").replace(new RegExp('(:?'+settings.key_validator+')','g'), "<your validator key>").replace(new RegExp('(:?'+settings.key_vote+')','g'), "<your vote key>").replace(new RegExp('(:?'+os.hostname()+')','g'), "<your hostname>")
	}
	console.log(res);
	return res;
}
function cmdFullName(abbr){
	var full_name = '%param%';
	for(var i = 0; i<cmd_arr.length; i++){
		if(cmd_arr[i].indexOf(abbr)>-1){
			message('cn0',cmd_arr[i][0]);
			full_name = cmd_arr[i][0];
			break;
		}
	}
	return full_name;
}
function cmdPrepare(cmd){
	var input_arr = cmd.split(/\s+/g);
	var cmd_keys = [];
	var cmd_params = [];
	for(var i = 0; i<input_arr.length; i++){
		var cmd_name = cmdFullName(input_arr[i]);
		if(cmd_name != '%param%'){
			//input_arr[i] = cmd_name;
			cmd_keys.push(cmd_name);
		} else {
			cmd_keys.push('%param%');
			cmd_params.push(input_arr[i]);
		}
	}
	return [cmd_keys,cmd_params];
}
function cmdExec(cmd){
	var input_arr = cmdPrepare(cmd.trim());
	var cmd_key = input_arr[0].join('_');
	var res;
	message('ce0',cmd_key);
	if (cmd_key.trim().startsWith('watch')){
		let args = input_arr[0].join(' ');
		args = args.replace('watch', '');
		message('ce1', args);
		watcher.task(args.trim().split(/\s+/g));
	} else if(settings[cmd_key]){
		message('ce2', settings[cmd_key]);
		var cmd_val = settings[cmd_key];
		for(var i = 0; i<input_arr[1].length; i++){
			message('ce3',i,input_arr[1][i]);
			cmd_val = cmd_val.replace(/%param%/,input_arr[1][i]);
		}
		for (const name of Object.keys(settings)) {
			let pattern = "%"+name+"%"
			let re = new RegExp(pattern, "g");
			cmd_val = cmd_val.replace(re, settings[name]);
		}
		res = cmd_val;
		try {
			res = execSync(cmd_val).toString("utf8");
		}catch(e){
			message('out', e);
		}
	} else {
		message('ce4', input_arr[0].join(' '));
	}
	return res;
}
function loadCmdAbbr(fileName) {
	try {
		fs.accessSync(fileName, fs.constants.R_OK | fs.constants.W_OK);
		let content = fs.readFileSync(fileName, 'utf8');
		let rows = content.split("\n");
		let tmpArr = [];
		for(let i = 0; i < rows.length; i++) {
			rows[i] = rows[i].trim();
			if(!rows[i].startsWith('//')){
				tmpArr.push(rows[i]);
			}
		}
		cmd_arr = JSON.parse('[["'+tmpArr.join(';').replace(/\s*,\s*/g,'","').replace(/\s*;\s*/g,'"],["')+'"]]');
		message('out', 'loaded:' + cmd_arr.length);
	} catch(e) {
		message('fa0', fileName);
		message('out', e);
	}
}
function init() {
	try {
		fs.accessSync(rootDir + '/messages.v', fs.constants.R_OK);
		let content = fs.readFileSync(rootDir + '/messages.v', 'utf8');
		let rows = content.split("\n");
		for(let i = 0; i < rows.length; i++) {
			rows[i] = rows[i].trim();
			if(!rows[i].startsWith('//')){
				let preIndex = rows[i].indexOf("=");
				let key = rows[i].substring(0, preIndex).toLowerCase().trim();
				let val = rows[i].substring(preIndex+1).trim();
				messages[key] = val;
			}
		}
		console.log(JSON.stringify(messages));
	} catch(e) {
		console.log(e);
	}
	let settingsPath = rootDir + '/settings.v'
	try {
		fs.accessSync(settingsPath, fs.constants.R_OK | fs.constants.W_OK);
		let content = fs.readFileSync(settingsPath, 'utf8');
		let rows = content.split("\n");
		for(let i = 0; i < rows.length; i++) {
			rows[i] = rows[i].trim();
			if(!rows[i].startsWith('//')){
				let preIndex = rows[i].indexOf("=");
				let key = rows[i].substring(0, preIndex).toLowerCase().trim().replace(/\s+/g, '_');
				let val = rows[i].substring(preIndex+1).trim();
				settings[key] = val;
				message('it0', key, val);
			}
		}
	} catch(e) {
		message('fa0', settingsPath);
		message('out', e);
	}
	const nets = os.networkInterfaces();
	for (const name of Object.keys(nets)) {
		for (const net of nets[name]) {
			if (net.family === 'IPv4' && !net.internal) {
				if (!net[name]) {
					netData[name] = [];
				}
				netData[name].push(net.address);
			}
		}
	}
	message('out',JSON.stringify(netData));
	if(typeof netData["WLAN"] != 'undefined'){
		settings.ip = netData["WLAN"][0];
	}
	if(typeof netData["eno1"] != 'undefined'){
		settings.ip = netData["eno1"][0];
	}
	if(typeof netData["enp6s0"] != 'undefined'){
		settings.ip = netData["enp6s0"][0];
	}
	settings.bot.options.certificate = settings.bot_certificate;
	if(settings.solana_key_path){
		settings.solana_key_path = settings.solana_key_path.trim().replace(/\\/g, '/');
		if(!settings.solana_key_path.endsWith('/')){
			settings.solana_key_path = settings.solana_key_path + '/';
		}
	}
	loadCmdAbbr(rootDir + '/cmd_abbr.v');
	settings['key_validator'] = cmdExec('key validator').trim();
	settings['key_vote'] = cmdExec('key vote').trim();
	try {
		var fileCrt = rootDir+'/ssl/my.key';
		fs.accessSync(fileCrt, fs.constants.R_OK);
		fileCrt = rootDir+'/ssl/my.pem';
		fs.accessSync(fileCrt, fs.constants.R_OK);
		message('it1',settings.telegram_token);
		bot = new TelegramBot(settings.telegram_token, settings.bot.options);
		message('it2',JSON.stringify(settings.bot.options));
		bot.onText(new RegExp('/'+settings.solana_app+' (.+)'), (msg, match) => {
			message('it3',msg);
			message('it4',match);
			const chatId = msg.chat.id;
			if(msg.from.username.toLowerCase() == settings.chat_access_username.toLowerCase()){
				settings.bot.chat_id = chatId;
				let answer = cmdExec(match[1]);
				message('it5',answer);
				if(answer){
					bot.sendMessage(chatId, message('out',answer));
				}
			} else {
				bot.sendMessage(chatId, 'access denay');
			}
		});
	} catch(e) {
		message('it6',rootDir,rootDir,settings.ip);
		message('out',e);
	}
}
init();
message('out',JSON.stringify(settings));