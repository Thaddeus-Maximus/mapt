window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
    document.getElementById("searchButton").addEventListener("click", runFindPins);
}

function runFindPins() {
  keyword = document.getElementById("searchBox").value
  console.log("Searching for", keyword)
  findPins(keyword).then((x) => {
  	// actually do something with the pins...
  	console.log("Found these pins:", x)
  })
}