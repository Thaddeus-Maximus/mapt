window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
    document.getElementById("searchButton").addEventListener("click", runFindPins);
    runFindPins()
}

function openPin(event) {
  pinId = event.target.dataset.pinId;
  console.log("openPin #", pinId)
}

function runFindPins() {
  let keyword = document.getElementById("searchBox").value
  console.log("Searching for", keyword)

  let types = null
  getTypes().then((foundTypes) => {
    types = foundTypes
    console.log("Found these types: ", foundTypes)
  })

  findPinsByType(keyword).then((foundPins) => {
  	// actually do something with the pins...
  	console.log("Found these pins:", foundPins)
    console.log("Found these types first: ", types)

    let searchResultsList = document.getElementById("searchResults");

    while (searchResultsList.firstChild)
      searchResultsList.removeChild(searchResultsList.firstChild)

    Object.keys(foundPins).forEach((type) => {
      let pinListSection = document.createElement("li");
      pinListSection.appendChild(document.createTextNode(types[type]["name"]));
      pinListSection.classList.add("typeListing")
      searchResultsList.appendChild(pinListSection);

      let pinListSectionList = document.createElement("ul");
      searchResultsList.appendChild(pinListSectionList)

      foundPins[type].forEach((pin) => {
        let pinListElement = document.createElement("li");
        pinListElement.appendChild(document.createTextNode(pin["name"]));
        pinListElement.classList.add("pinListing")
        pinListElement.addEventListener("click", openPin)
        pinListElement.dataset.pinId = pin["id"]
        pinListSectionList.appendChild(pinListElement);
      })
    })
  })
}