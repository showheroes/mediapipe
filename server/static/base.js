function initiateProgressSocket(progressWindow, taskID, deployPath) {
	let host = getBaseURL();
	let socketPath = "wss://" + host + deployPath + "/tasks/" + taskID + "/progress";
	let socket = new WebSocket(socketPath);
	var intervalHandler;
	var spinnerSpan = $('span');
	spinnerSpan.attr('id', 'progressSpinner')
	spinnerSpan.addClass('spinner-grow spinner-grow-sm mr-4');
	spinnerSpan.attr('role','status');
	spinnerSpan.attr('aria-hidden', 'true');

	// handlers
	socket.onopen = function(e) {
		progressWindow.append(spinnerSpan);
		intervalHandler = setInterval(() => {
			socket.send(JSON.stringify({command: "progress"}));
		}, 1500);
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

	socket.onmessage = function(event) {
	    message = JSON.parse(event.data);
        progressWindow.html(message.data);
	    switch(message.type) {
	        case "progress":
                progressWindow.append(spinnerSpan);
                break;
            case "complete":
                socket.close();
                break;
	    }
		window.scrollTo(0, document.body.scrollHeight);
	};

}

function getBaseURL() {
	return window.location.host;
}

$(document).ready(function () {
$('#task-list').DataTable();
$('.dataTables_length').addClass('bs-select');
});