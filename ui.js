window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
    document.getElementById("searchButton").addEventListener("click", runFindPins);
}

function runFindPins() {
  let keyword = document.getElementById("searchBox").value
  console.log("Searching for", keyword)
  findPins(keyword).then((foundPins) => {
  	// actually do something with the pins...
  	console.log("Found these pins:", foundPins)
  })
}