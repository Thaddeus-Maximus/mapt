window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
  document.getElementById("searchButton").addEventListener("click", runFindPins);
  runFindPins()
  document.getElementById("detailEdit").addEventListener("click", editActiveDetail);
}

function loadSvgToMap(url, map)
{
  try{
    let req=new XMLHttpRequest();
    req.onreadystatechange=function()
    {  
      try{
        if(req.readyState == 4)
        {   if(req.status == 200)
            {
              while (map.firstChild)
                map.removeChild(map.firstChild)
              map.appendChild(req.responseXML.documentElement);
            }
            else
            {   console.log("URL "+url+" not available");
            }
        }
      }catch(e){
        console.log("Error parsing SVG: ", e)
      }
    }
    req.open("POST", url, true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.send();
  }catch(e){
    console.log("Error loading SVG: ", e)
  }
}

function editActiveDetail(event) {
  console.log("editActiveDetail", event)
}

function openPin(event) {
  pinId = event.target.dataset.pinId;

  getPin(pinId).then((pin) => {
    let table = document.getElementById("detailTable")
    while (table.firstChild)
      table.removeChild(table.firstChild)

    function addContent(key, val) {
      let tr = document.createElement("tr")
      let title   = document.createElement("td")
      let content = document.createElement("td")

      title.appendChild(document.createTextNode(key))
      if (typeof val == "string"){
        content.appendChild(document.createTextNode(val))
      } else {
        content.appendChild(val)
      }

      tr.appendChild(title)
      tr.appendChild(content)
      table.appendChild(tr)
    }

    getType(pin.type).then((type) => {
      addContent("Type", type.name)
      if (pin.parent != null) {
        let link = document.createElement("a")
        link.dataset.pinId = pin.parent
        link.addEventListener("click", openPin)
        addContent("Located In", link)
        getPin(pin.parent).then((parentPin) => {
          link.appendChild(document.createTextNode(parentPin.name))
        })
      }

      type.fields.forEach((field) => {
        addContent(field, pin.fields[field])
      })

      if (type.name.toLowerCase() == "area" || type.name.toLowerCase() == "space") {
        loadSvgToMap(pin.image, document.getElementById("mapImage"))
      }
    })

    document.getElementById("detailTitle").innerHTML = pin.name;
    document.getElementById("detailImage").src = pin.image;
  })
}

function runFindPins() {
  let keyword = document.getElementById("searchBox").value

  let types = null
  getTypes().then((foundTypes) => {
    types = foundTypes
  })

  findPinsByType(keyword).then((foundPins) => {
    let searchResultsList = document.getElementById("searchResults");

    while (searchResultsList.firstChild)
      searchResultsList.removeChild(searchResultsList.firstChild)

    Object.keys(foundPins).forEach((type) => {
      let pinListSection = document.createElement("li");
      pinListSection.appendChild(document.createTextNode(types[type].name));
      pinListSection.classList.add("typeListing")
      pinListSection.style.color = types[type].color
      searchResultsList.appendChild(pinListSection);

      let pinListSectionList = document.createElement("ul");
      searchResultsList.appendChild(pinListSectionList)

      foundPins[type].forEach((pin) => {
        let pinListElement = document.createElement("li");
        let link = document.createElement("a");

        link.appendChild(document.createTextNode(pin["name"]));
        link.classList.add("pinListing")
        link.addEventListener("click", openPin)
        link.dataset.pinId = pin["id"]

        pinListElement.appendChild(link);
        pinListSectionList.appendChild(pinListElement);
      })
    })
  })
}