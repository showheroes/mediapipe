function initiateProgressSocket(textarea, taskID) {
	let host = getBaseURL();
	let socket = new Websocket("wss://" + host + "/video/ui/reformat/tasks/ " + taskID + "/progress");

	socket.onopen = function(e) {
		console.log("initiated progress socket");
		socket.send("progress");
	};

	socket.onmessage = function(event) {
		console.log("[Progress] " + event.data);
		$(textarea).val(event.data);
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

}

function getBaseURL() {
	return window.location.host;
}
