

const AREA_TYPE = "Area"
const DEFAULT_TYPE = "Tools"

const TYPES = {
	"Area": {
		color: "#964B00",
		fields: [
			"Description",
			"Manager"
		]
	},
	"Supplies": {
		color: "#180",
		fields: [
			"Description",
			"Manager",
			"Contents"
		]
	},
	"Tools": {
		color: "#23d",
		fields: [
			"Description",
			"Manager",
			"Make/Model",
			"Checkout List"
		]
	},
	"Plot": {
		color: "#70a",
		fields: [
			"Owner"
		]
	},
	"Computer": {
		color: "#246",
		fields: [
			"Description",
			"Manager"
		]
	},
	"Safety": {
		color: "#d90",
		fields: [
			"Description",
			"Manager"
		]
	},
	"Utilities": {
		color: "#d35",
		fields: [
			"Description",
			"Manager",
			"Service Schedule"
		]
	}
}


const DEFAULT_PIN_DATA = {
"parent": null,
"type": DEFAULT_TYPE,
"name": "new_pin",
"image": null,
"fields": TYPES[DEFAULT_TYPE].fields,
"coords": [{x:0, y:0}]
}

const NULL_IMAGE_URL = "assets/null.svg"
const UNIVERSE_IMAGE_URL = "assets/universe.svg"
const SEARCH_SPLIT_REGEX = /[^A-Za-z0-9]/

function keywordSplit(x) {
	let splits = x.toLowerCase().split(SEARCH_SPLIT_REGEX)
	if (splits.includes("woodshop")){
		splits.push("wood")
		splits.push("shop")
	}
	if (splits.includes("metalshop")) {
		splits.push("metal")
		splits.push("shop")
	}
	if (splits.includes("millbit")) {
		splits.push("mill")
		splits.push("bit")
	}
	if (splits.includes("drillbit")) {
		splits.push("drill")
		splits.push("bit")
	}
	return splits
}