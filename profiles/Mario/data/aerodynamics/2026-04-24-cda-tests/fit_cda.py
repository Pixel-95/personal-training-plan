#!/usr/bin/env python3
"""Fit Crr and CdA for Mario's current 24° forearm setup."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares


G = 9.80665
R_DRY_AIR = 287.05
R_WATER_VAPOR = 461.495


@dataclass(frozen=True)
class Environment:
    rider_mass_kg: float = 82.7
    bike_mass_kg: float = 13.0
    temperature_c: float = 18.0
    humidity_rel: float = 0.30
    pressure_hpa: float = 1023.0
    drivetrain_efficiency_mean: float = 0.975
    drivetrain_efficiency_sigma: float = 0.005

    @property
    def total_mass_kg(self) -> float:
        return self.rider_mass_kg + self.bike_mass_kg


@dataclass(frozen=True)
class Dataset:
    speed_kmh: np.ndarray
    speed_err_kmh: np.ndarray
    power_w: np.ndarray
    power_err_w: np.ndarray

    @property
    def speed_mps(self) -> np.ndarray:
        return self.speed_kmh / 3.6

    @property
    def speed_err_mps(self) -> np.ndarray:
        return self.speed_err_kmh / 3.6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit CdA for Mario's 24° forearm setup.")
    parser.add_argument("--data", type=Path, default=Path("data.dat"))
    parser.add_argument("--mc-samples", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_dataset(path: Path) -> Dataset:
    data = np.loadtxt(path, skiprows=2)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] != 4:
        raise ValueError(f"{path} must contain speed, speed error, power and power error.")
    return Dataset(data[:, 0], data[:, 1], data[:, 2], data[:, 3])


def saturation_vapor_pressure_pa(temperature_c: float) -> float:
    return 610.94 * math.exp((17.625 * temperature_c) / (temperature_c + 243.04))


def air_density(environment: Environment) -> float:
    temperature_k = environment.temperature_c + 273.15
    vapor_pressure = environment.humidity_rel * saturation_vapor_pressure_pa(environment.temperature_c)
    dry_air_pressure = environment.pressure_hpa * 100.0 - vapor_pressure
    return (
        dry_air_pressure / (R_DRY_AIR * temperature_k)
        + vapor_pressure / (R_WATER_VAPOR * temperature_k)
    )


def pedal_power(
    speed_mps: np.ndarray,
    crr: float,
    cda: float,
    density: float,
    environment: Environment,
    drivetrain_efficiency: float,
) -> np.ndarray:
    wheel_power = (
        0.5 * density * cda * speed_mps**3
        + crr * environment.total_mass_kg * G * speed_mps
    )
    return wheel_power / drivetrain_efficiency


def residuals(
    parameters: np.ndarray,
    dataset: Dataset,
    density: float,
    environment: Environment,
    drivetrain_efficiency: float,
) -> np.ndarray:
    crr, cda = parameters
    predicted = pedal_power(
        dataset.speed_mps,
        crr,
        cda,
        density,
        environment,
        drivetrain_efficiency,
    )
    wheel_gradient = (
        1.5 * density * cda * dataset.speed_mps**2
        + crr * environment.total_mass_kg * G
    )
    pedal_gradient = wheel_gradient / drivetrain_efficiency
    effective_sigma = np.sqrt(
        dataset.power_err_w**2 + (pedal_gradient * dataset.speed_err_mps) ** 2
    )
    return (dataset.power_w - predicted) / effective_sigma


def fit(
    dataset: Dataset,
    density: float,
    environment: Environment,
    drivetrain_efficiency: float,
    initial: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    result = least_squares(
        residuals,
        x0=np.array([0.0055, 0.214]) if initial is None else initial,
        bounds=([0.0, 0.10], [0.02, 0.60]),
        args=(dataset, density, environment, drivetrain_efficiency),
        max_nfev=10000,
    )
    degrees_of_freedom = dataset.speed_kmh.size - result.x.size
    reduced_chi2 = 2.0 * result.cost / degrees_of_freedom
    return result.x, reduced_chi2


def monte_carlo(
    dataset: Dataset,
    density: float,
    environment: Environment,
    best: np.ndarray,
    samples: int,
    seed: int,
) -> np.ndarray:
    random = np.random.default_rng(seed)
    draws: list[np.ndarray] = []
    for _ in range(samples):
        sampled = Dataset(
            speed_kmh=random.normal(dataset.speed_kmh, dataset.speed_err_kmh),
            speed_err_kmh=dataset.speed_err_kmh,
            power_w=random.normal(dataset.power_w, dataset.power_err_w),
            power_err_w=dataset.power_err_w,
        )
        efficiency = float(
            np.clip(
                random.normal(
                    environment.drivetrain_efficiency_mean,
                    environment.drivetrain_efficiency_sigma,
                ),
                0.94,
                0.995,
            )
        )
        parameters, _ = fit(sampled, density, environment, efficiency, best)
        draws.append(parameters)
    return np.vstack(draws)


def speed_at_power(
    target_power: float,
    crr: float,
    cda: float,
    density: float,
    environment: Environment,
) -> float:
    def difference(speed_kmh: float) -> float:
        power = pedal_power(
            np.array([speed_kmh / 3.6]),
            crr,
            cda,
            density,
            environment,
            environment.drivetrain_efficiency_mean,
        )[0]
        return float(power - target_power)

    return float(brentq(difference, 10.0, 70.0))


def main() -> None:
    args = parse_args()
    environment = Environment()
    dataset = load_dataset(args.data)
    density = air_density(environment)
    best, reduced_chi2 = fit(
        dataset,
        density,
        environment,
        environment.drivetrain_efficiency_mean,
    )
    draws = monte_carlo(dataset, density, environment, best, args.mc_samples, args.seed)
    median = np.median(draws, axis=0)
    lower = median - np.percentile(draws, 16, axis=0)
    upper = np.percentile(draws, 84, axis=0) - median
    crr, cda = median
    power_40 = pedal_power(
        np.array([40.0 / 3.6]),
        crr,
        cda,
        density,
        environment,
        environment.drivetrain_efficiency_mean,
    )[0]

    print("Setup: 24 degree forearm tilt")
    print(f"Crr: {crr:.5f} -{lower[0]:.5f}/+{upper[0]:.5f}")
    print(f"CdA: {cda:.4f} -{lower[1]:.4f}/+{upper[1]:.4f} m^2")
    print(f"Reduced chi^2: {reduced_chi2:.3f}")
    print(f"Power at 40 km/h: {power_40:.1f} W")
    print(f"Speed at 230 W: {speed_at_power(230.0, crr, cda, density, environment):.2f} km/h")


if __name__ == "__main__":
    main()
