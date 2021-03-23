

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
		color: "#090",
		fields: [
			"Description",
			"Manager",
			"Contents"
		]
	},
	"Tools": {
		color: "#b00",
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
	}
}


const DEFAULT_PIN_DATA = {
"parent": null,
"type": DEFAULT_TYPE,
"name": "new_pin",
"picture": "null.svg",
"fields": TYPES[DEFAULT_TYPE].fields,
"coords": [{x:0, y:0}]
}