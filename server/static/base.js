function initiateProgressSocket(progressWindow, taskID, deployPath) {
	let host = getBaseURL();
	let socketPath = "ws://" + host + "/" + deployPath + "/video/flip/ui/tasks/" + taskID + "/progress";
	let socket = new WebSocket(socketPath);
	var intervalHandler;
	socket.onopen = function(e) {
		intervalHandler = setInterval(() => {
			socket.send("progress");
			var spinnerSpan = $('span');
			spinnerSpan.addClass('spinner-grow spinner-grow-sm mr-4');
			spinnerSpan.attr('role','status');
			spinnerSpan.attr('aria-hidden', 'true');
			progressWindow.append(spinnerSpan);
			console.log("[action] reloading progress");
		}, 1500);
	};

	socket.onmessage = function(event) {
		progressWindow.html(event.data);
		window.scrollTo(0, document.body.scrollHeight);
	};

	socket.onclose = function(event) {
	  if (event.wasClean) {
	    console.log(`[close] Connection closed cleanly, code=${event.code} reason=${event.reason}`);
	  } else {
	    // e.g. server process killed or network down
	    // event.code is usually 1006 in this case
	    console.log('[close] Connection died');
	  }
		clearInterval(intervalHandler);
	};
}

function getBaseURL() {
	return window.location.host;
}
