export type ComponentId =
  | "engine"
  | "battery"
  | "brakes"
  | "fuel"
  | "mileage"
  | "diagnostics"
  | "service";

export interface ComponentItem {
  id: ComponentId;
  code: string;
  label: string;
  shortLabel: string;
  value: string;
  sub: string;
  impact: string;
  positive: boolean;
}

export const COMPONENTS: ComponentItem[] = [
  {
    id: "engine",
    code: "ENG",
    label: "Engine & transmission",
    shortLabel: "Engine",
    value: "4.0L V8 BiTurbo",
    sub: "Oil life 62% - 0 faults",
    impact: "+RM 18,400",
    positive: true,
  },
  {
    id: "battery",
    code: "BAT",
    label: "Battery/electrical",
    shortLabel: "Battery",
    value: "12V system",
    sub: "SOH 94% - alternator OK",
    impact: "+RM 6,200",
    positive: true,
  },
  {
    id: "brakes",
    code: "BRK",
    label: "Brakes & suspension",
    shortLabel: "Brakes",
    value: "Sport suspension",
    sub: "Rotor wear normal",
    impact: "+RM 4,900",
    positive: true,
  },
  {
    id: "fuel",
    code: "FUE",
    label: "Fuel type & consumption",
    shortLabel: "Fuel",
    value: "Petrol V8",
    sub: "Fuel trim within range",
    impact: "-RM 2,100",
    positive: false,
  },
  {
    id: "mileage",
    code: "ODO",
    label: "Mileage/odometer (OBD)",
    shortLabel: "Odometer",
    value: "45,320 km",
    sub: "OBD agrees with profile",
    impact: "+RM 9,800",
    positive: true,
  },
  {
    id: "diagnostics",
    code: "DTC",
    label: "Diagnostics fault codes",
    shortLabel: "Diagnostics",
    value: "ODX status report",
    sub: "1 informational signal",
    impact: "-RM 1,600",
    positive: false,
  },
  {
    id: "service",
    code: "SVC",
    label: "Service history",
    shortLabel: "Service",
    value: "6 of 7 records",
    sub: "Assumption adjustment only",
    impact: "+RM 11,200",
    positive: true,
  },
];

export function getComponent(id: ComponentId) {
  return COMPONENTS.find((item) => item.id === id) ?? COMPONENTS[0];
}
