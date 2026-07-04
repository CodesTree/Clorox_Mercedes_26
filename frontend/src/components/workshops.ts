export interface VehicleLocation {
  label: string;
  area: string;
  lat: number;
  lng: number;
}

export interface MercedesWorkshop {
  id: string;
  name: string;
  area: string;
  address: string;
  lat: number;
  lng: number;
  nextSlot: string;
}

export interface RankedWorkshop extends MercedesWorkshop {
  distanceKm: number;
  mapX: number;
  mapY: number;
}

export const currentVehicleLocation: VehicleLocation = {
  label: "Current OBD location",
  area: "KLCC, Kuala Lumpur",
  lat: 3.1579,
  lng: 101.7123,
};

const mercedesWorkshops: MercedesWorkshop[] = [
  {
    id: "hap-seng-star-kl",
    name: "Hap Seng Star KL",
    area: "Jalan Sultan Ismail",
    address: "Official Mercedes-Benz centre near KLCC",
    lat: 3.1537,
    lng: 101.708,
    nextSlot: "Fri 10 Jul, 10:00 AM",
  },
  {
    id: "nz-wheels-bangsar",
    name: "NZ Wheels Bangsar",
    area: "Bangsar",
    address: "Official Mercedes-Benz service centre",
    lat: 3.1279,
    lng: 101.675,
    nextSlot: "Fri 10 Jul, 2:30 PM",
  },
  {
    id: "cycle-carriage-mutiara",
    name: "Cycle & Carriage Mutiara Damansara",
    area: "Mutiara Damansara",
    address: "Mercedes-Benz service and inspection centre",
    lat: 3.163,
    lng: 101.6115,
    nextSlot: "Sat 11 Jul, 9:30 AM",
  },
  {
    id: "hap-seng-star-balakong",
    name: "Hap Seng Star Balakong",
    area: "Balakong",
    address: "Mercedes-Benz service and repair centre",
    lat: 3.0362,
    lng: 101.7542,
    nextSlot: "Sat 11 Jul, 11:00 AM",
  },
];

function toRadians(value: number) {
  return (value * Math.PI) / 180;
}

function distanceKm(from: VehicleLocation, to: MercedesWorkshop) {
  const earthRadiusKm = 6371;
  const deltaLat = toRadians(to.lat - from.lat);
  const deltaLng = toRadians(to.lng - from.lng);
  const fromLat = toRadians(from.lat);
  const toLat = toRadians(to.lat);

  const haversine =
    Math.sin(deltaLat / 2) ** 2 + Math.cos(fromLat) * Math.cos(toLat) * Math.sin(deltaLng / 2) ** 2;

  return 2 * earthRadiusKm * Math.asin(Math.sqrt(haversine));
}

export function getRankedWorkshops(location = currentVehicleLocation): RankedWorkshop[] {
  const points = [location, ...mercedesWorkshops];
  const minLat = Math.min(...points.map((point) => point.lat));
  const maxLat = Math.max(...points.map((point) => point.lat));
  const minLng = Math.min(...points.map((point) => point.lng));
  const maxLng = Math.max(...points.map((point) => point.lng));
  const latRange = maxLat - minLat || 1;
  const lngRange = maxLng - minLng || 1;

  return mercedesWorkshops
    .map((workshop) => ({
      ...workshop,
      distanceKm: distanceKm(location, workshop),
      mapX: 12 + ((workshop.lng - minLng) / lngRange) * 76,
      mapY: 88 - ((workshop.lat - minLat) / latRange) * 76,
    }))
    .sort((a, b) => a.distanceKm - b.distanceKm);
}

export function formatDistanceKm(value: number) {
  return `${value.toFixed(1)} km away`;
}
