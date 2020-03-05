function initiateProgressSocket(progressWindow, taskID, deployPath) {
	let host = getBaseURL();
	let socketPath = "ws://" + host + "/" + deployPath + "/video/flip/ui/tasks/" + taskID + "/progress";
	let socket = new WebSocket(socketPath);
	socket.onopen = function(e) {
		socket.send("progress");
	};

	socket.onmessage = function(event) {
		progressWindow.html(event.data);
	};

	socket.onclose = function(event) {
	  if (event.wasClean) {
	    alert(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
	  } else {
	    // e.g. server process killed or network down
	    // event.code is usually 1006 in this case
	    alert('[close] Connection died');
	  }
	};
	window.setInterval(function(){
		socket.send("progress")
	}, 1500);
}

function getBaseURL() {
	return window.location.host;
}
