function initiateProgressSocket(progressWindow, taskID, deployPath) {
	let host = getBaseURL();
	let socketPath = "ws://" + host + "/" + deployPath + "/video/flip/ui/tasks/" + taskID + "/progress";
	let socket = new WebSocket(socketPath);
	socket.onopen = function(e) {
		window.setInterval(function(){
			socket.send("progress");
			console.log("[action] reloading progress");
		}, 1500);
	};

	socket.onmessage = function(event) {
		progressWindow.html(event.data);
	};

	socket.onclose = function(event) {
	  if (event.wasClean) {
	    console.log(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
	  } else {
	    // e.g. server process killed or network down
	    // event.code is usually 1006 in this case
	    console.log('[close] Connection died');
	  }
	};
}

function getBaseURL() {
	return window.location.host;
}
