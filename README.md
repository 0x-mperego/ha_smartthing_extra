# SmartThings Extra — mperego fork

Fork of `mik-laj/ha_smartthing_extra` for Home Assistant.

It reuses the **official Home Assistant SmartThings integration and its authenticated push client**. No additional Samsung login or Personal Access Token is required.

## Added in this fork

Read-only Samsung cooktop entities for custom SmartThings capabilities that Home Assistant does not currently expose:

- per-zone countdown timer remaining (`samsungce.countDownTimer.currentValue`)
- per-zone countdown timer initially set (`startValue`)
- per-zone timer status (`status`)
- per-zone residual heat (`samsungce.surfaceResidualHeat`)

The sensors subscribe to SmartThings capability events, so timer changes are push-driven rather than periodically polling Samsung.

Initial test target: Samsung NZ64B5066KK.

The original oven clock-sync and generic SmartThings command services are retained from upstream.

## Installation

Add `0x-mperego/ha_smartthing_extra` to HACS as a custom **Integration**, install it, restart Home Assistant, then add **SmartThings Extra** from Settings > Devices & services.

## Safety

The cooktop additions in this fork are read-only. They do not add remote burner or cooktop power controls.

## License

MIT
