window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
  document.getElementById("searchButton").addEventListener("click", runFindPins);
  document.getElementById("pinEdit").addEventListener("click", editActivePin);
  document.getElementById("pinSave").addEventListener("click", saveActivePin);
  document.getElementById("pinCancel").addEventListener("click", cancelActivePin);
  document.getElementById("pinDelete").addEventListener("click", deleteActivePin);
  document.getElementById("newPin").addEventListener("click", makeNewPin);
  document.getElementById("pinImageUpload").addEventListener("change", loadNewPinImage)
  document.getElementById("loginButton").addEventListener("click", logIn)
  runFindPins();
}


/*
 * Firebase auth
 */ 

var uiConfig = {
  signInSuccessUrl: '<url-to-redirect-to-on-success>',
  signInOptions: [
    // Leave the lines as is for the providers you want to offer your users.
    firebase.auth.GoogleAuthProvider.PROVIDER_ID,
    firebase.auth.FacebookAuthProvider.PROVIDER_ID,
    firebase.auth.TwitterAuthProvider.PROVIDER_ID,
    firebase.auth.GithubAuthProvider.PROVIDER_ID,
    firebase.auth.EmailAuthProvider.PROVIDER_ID,
    firebase.auth.PhoneAuthProvider.PROVIDER_ID,
    firebaseui.auth.AnonymousAuthProvider.PROVIDER_ID
  ],
  // tosUrl and privacyPolicyUrl accept either url string or a callback
  // function.
  // Terms of service url/callback.
  tosUrl: '<your-tos-url>',
  // Privacy policy url/callback.
  privacyPolicyUrl: function() {
    window.location.assign('<your-privacy-policy-url>');
  }
};

// Initialize the FirebaseUI Widget using Firebase.
//var ui = new firebaseui.auth.AuthUI(firebase.auth());
// The start method will wait until the DOM is loaded.
//ui.start('#firebaseui-auth-container', uiConfig);

function logIn(event) {
  let email = window.prompt("Please provide your email.")
  if (email != window.prompt("Please confirm your email.")) {
    window.alert("Emails do not match.")
    return null;
  }

  let password = window.prompt("Please provide your password.")
  if (password != window.prompt("Please confirm your password.")) {
    window.alert("Emails do not match.")
    return null;
  }

  console.log(window.location.href)
  console.log(email)
  firebase.auth().createUserWithEmailAndPassword(email, password).then((result) => {
    window.alert("Welcome aboard. An admin must approve you for edit access.")
  }).catch((error) => {
    console.log(error)
  })
  
}

/*
 * Utility functions
 */

function buildSelectList(options, values) {
  const select = document.createElement("select")
  if (values) {
    for (let i=0; i<options.length; i++) {
      const optionElement = document.createElement("option");

      optionElement.textContent = options[i];
      optionElement.value = values[i]

      select.appendChild(optionElement)
    }
  } else if (Array.isArray(options)) {
    for (let i=0; i<options.length; i++) {
      const optionElement = document.createElement("option");

      optionElement.textContent = options[i];
      optionElement.value = options[i]

      select.appendChild(optionElement)
    }
  } else {
    for (const option in options) {
      const optionElement = document.createElement("option");

      optionElement.textContent = option;
      optionElement.value = options[option]

      select.appendChild(optionElement)
    }
  }
  return select
}

/*
 * CRUD
 */

// Display pin pins
function populatePins(pin) {
  const table = document.getElementById("pinTable")
  while (table.firstChild)
    table.removeChild(table.firstChild)

  function addContent(key, val) {
    const tr = document.createElement("tr")
    const title   = document.createElement("td")
    const content = document.createElement("td")

    title.appendChild(document.createTextNode(key))
    if (typeof val == "string"){
      content.dataset.raw = val;
      content.innerHTML = marked(val);
    } else {
      content.appendChild(val)
    }

    tr.appendChild(title)
    tr.appendChild(content)
    table.appendChild(tr)
  }
  
  addContent("Type", pin.type)

  const link = document.createElement("a")
  addContent("Located In", link)

  if (pin.parent != null) {
    link.dataset.pinId = pin.parent
    link.addEventListener("click", openPin)
    getPin(pin.parent).then((parentPin) => {
      link.appendChild(document.createTextNode(parentPin.name))
    })
  }

  TYPES[pin.type].fields.forEach((field, i) => {
    addContent(field, pin.fields[i])
  })

  document.getElementById("pinTitle").innerHTML = "<h3>"+pin.name+"</h3>";

  function loadPinImage(url) {
    const image = document.getElementById("pinImage")
    image.setAttribute("src", url);
    image.dataset.modified = "";
  }

  function loadMapImage(url) {
    document.getElementById("mapImage").setAttribute("src", url);
  }

  if (pin.image) {
    document.getElementById("pinImage").dataset.name = pin.image
    storageRef.child('images/'+pin.image).getDownloadURL().then(loadPinImage)
  }
  else{
    loadPinImage(NULL_IMAGE_URL)
  }

  if (pin.parent) {
    getPin(pin.parent).then((parentPin) => {
      if (parentPin.image) {
        storageRef.child('images/'+parentPin.image).getDownloadURL().then(loadMapImage)
      } else {
        loadMapImage(NULL_IMAGE_URL)
      }
    })
  } else {
    loadMapImage(UNIVERSE_IMAGE_URL)
  }
}

// Delete active pin
function deleteActivePin(event) {
  pinId = document.getElementById("pinPane").dataset.pinId
  if (confirm("Are you sure you want to delete pin " + pinId + "?")) {
    deletePin(pinId);
    runFindPins();
  }
}

// Edit active pin
function editActivePin(event, pin) {
  document.getElementById("pinEdit").style.display = "none"
  document.getElementById("pinSave").style.display = ""
  document.getElementById("pinDelete").style.display = ""
  document.getElementById("pinCancel").style.display = ""
  document.getElementById("pinImageUpload").style.display = ""

  function convertToEdit(pin) {
    const title = document.getElementById("pinTitle")
    const titleEdit = document.createElement("input")
    
    titleEdit.value = title.firstChild.innerHTML
    while (title.firstChild)
      title.removeChild(title.firstChild)

    title.appendChild(titleEdit)

    const table = document.getElementById("pinTable")
    let textareas = []
    for (let i=0; i<table.children.length; i++) {
      let header = table.children[i].children[0]
      let content = table.children[i].children[1]
      
      if (i == 0) {
        let currentType = content.firstChild.innerHTML
        while (content.firstChild)
          content.removeChild(content.firstChild)

        let selectElement = buildSelectList(Object.keys(TYPES))
        selectElement.value = currentType
        selectElement.addEventListener("change", (event) => {
          const fields = TYPES[event.target.value].fields;
          while (table.children.length > 2)
            table.removeChild(table.children[2])

          for (let i=0; i<fields.length; i++) {
            const tr      = document.createElement("tr")
            const title   = document.createElement("td")
            const content = document.createElement("td")

            title.appendChild(document.createTextNode(fields[i]))
            if (textareas.length > i){
              content.appendChild(textareas[i])
            } else {
              let textarea = document.createElement("textarea")
              textarea.value = ""
              content.appendChild(textarea)
              textareas.push(textarea)
            }

            tr.appendChild(title)
            tr.appendChild(content)
            table.appendChild(tr)
          }
        })
        content.appendChild(selectElement)
      } else if (i == 1) {
        let currentParent = content.firstChild.innerHTML
        while (content.firstChild)
          content.removeChild(content.firstChild)

        findAreas().then((areas) => {
          let selectElement = buildSelectList({"<none>": null, ...areas})
          selectElement.value = areas[currentParent]
          content.appendChild(selectElement)
        })
      } else {
        let currentText = content.dataset.raw
        while (content.firstChild)
          content.removeChild(content.firstChild)

        let textarea = document.createElement("textarea")
        textarea.value = currentText
        content.appendChild(textarea)
        textareas.push(textarea)
      }
    }
  }

  if (pin)
    convertToEdit(pin)
  else
    getPin(document.getElementById("pinPane").dataset.pinId).then(convertToEdit)
}

function cancelActivePin(event) {
  openPin(null, document.getElementById("pinPane").dataset.pinId, null)
}

// Save active pin
function saveActivePin(event) {
  const table = document.getElementById("pinTable")
  const pinId = document.getElementById("pinPane").dataset.pinId
  const image = document.getElementById("pinImage")
  pin = {
    "fields": [],
    "name": document.getElementById("pinTitle").firstChild.value
  }

  for (let i=0; i<table.children.length; i++) {
    let header = table.children[i].children[0]
    let content = table.children[i].children[1]
    
    if (i == 0) {
      pin["type"] = content.firstChild.value
    } else if (i == 1) {
      pin["parent"] = content.firstChild.value
    } else {
      pin.fields[i-2] = content.firstChild.value
    }
  }

  if (image.dataset.modified) {
    // TODO: Zombies as a result of changing file extensions
    const filename = pinId+'.'+uploadedImage.name.split(/[. ]+/).pop()
    pin.image = filename
    storageRef.child("images/"+filename).put(uploadedImage).then((snapshot) => {
    })
  } else {
    pin.image = image.dataset.name
  }

  sendPin(pinId, pin).then((result) => {
    populatePins(pin)
    document.getElementById("pinPane").dataset.pinId = pinId
  })

  document.getElementById("pinEdit").style.display = ""
  document.getElementById("pinSave").style.display = "none"
  document.getElementById("pinDelete").style.display = ""
  document.getElementById("pinCancel").style.display = "none"
  document.getElementById("pinImageUpload").style.display = "none"
}

// Load pin from user's filesystem
let uploadedImage = null

function loadNewPinImage(event) {
  var image = document.getElementById('pinImage');
  image.src = URL.createObjectURL(event.target.files[0]);
  uploadedImage = event.target.files[0]
  image.dataset.modified = "yes";
  //image.dataset.imageurl = image.src
};

// Display the selected pin
function openPin(event, pinId, pin) {
  if (event) {
    getPin(event.target.dataset.pinId).then(populatePins)
    document.getElementById("pinPane").dataset.pinId = event.target.dataset.pinId
  }

  else if (pinId) {
    getPin(pinId).then(populatePins)
    document.getElementById("pinPane").dataset.pinId = pinId
  }

  else {
    populatePins(pin)
    document.getElementById("pinPane").dataset.pinId = pinId
  }

  document.getElementById("pinEdit").style.display = ""
  document.getElementById("pinSave").style.display = "none"
  document.getElementById("pinDelete").style.display = ""
  document.getElementById("pinCancel").style.display = "none"
  document.getElementById("pinImageUpload").style.display = "none"
}

// Make a new pin: Display a default pin and get into edit mode
function makeNewPin() {
  openPin(null, "", DEFAULT_PIN_DATA)
  editActivePin(null, DEFAULT_PIN_DATA)
}

// Run search on all pins, show the first one in pin
function runFindPins() {
  const keyword = document.getElementById("searchBox").value

  findPinsByType(keyword).then((foundPins) => {
    const searchResultsList = document.getElementById("searchResults");

    while (searchResultsList.firstChild)
      searchResultsList.removeChild(searchResultsList.firstChild)

    let first = true
    Object.keys(foundPins).forEach((type) => {
      const pinListSection = document.createElement("li");
      pinListSection.appendChild(document.createTextNode(type));
      pinListSection.classList.add("typeListing")
      pinListSection.style.color = TYPES[type].color
      searchResultsList.appendChild(pinListSection);

      const pinListSectionList = document.createElement("ul");
      searchResultsList.appendChild(pinListSectionList)

      foundPins[type].forEach((pin) => {
        if (first) {
          openPin(null, pin.id, pin)
          first = false
        }
        const pinListElement = document.createElement("li");
        const link = document.createElement("a");

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