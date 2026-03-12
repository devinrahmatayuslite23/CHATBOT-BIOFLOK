/**
 * =========================================================================
 * 🐟 FEED CALCULATOR ENGINE (GOOGLE APPS SCRIPT EDITION)
 * =========================================================================
 * Mengadopsi logika feed_calculator.py ke server Google.
 */

const FEED_PRICES = { starter: 18500, grower_1: 11500, grower_2: 11000 };
const getFeedPrice = (avg_weight_g) => avg_weight_g < 25 ? FEED_PRICES.starter : (avg_weight_g < 100 ? FEED_PRICES.grower_1 : FEED_PRICES.grower_2);
const getFeedRate = (avg_weight_g) => {
    if (avg_weight_g < 25) return [5.0, 5.0];
    if (avg_weight_g < 250) return [2.5, 2.5];
    if (avg_weight_g < 400) return [2.0, 2.5];
    return [1.5, 2.0];
};

function fc_getLatestSampling(ss) {
    const sheet = ss.getSheetByName("Sampling");
    if (!sheet) return null;
    const data = sheet.getDataRange().getValues();
    if (data.length < 2) return null;
    
    // Find last row that has weight > 0
    for (let i = data.length - 1; i >= 1; i--) {
        let weight = parseFloat(data[i][2].toString().replace(",", "."));
        if (!isNaN(weight) && weight > 0) {
            return {
                avg_weight_g: weight,
                avg_length_cm: parseFloat(data[i][3].toString().replace(",", ".")) || 0
            };
        }
    }
    return null;
}

function getFeedRecommendationApi(user_avg_weight_g) {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let weight = parseFloat(user_avg_weight_g);
    
    if (isNaN(weight) || weight <= 0) {
        let samp = fc_getLatestSampling(ss);
        if (samp && samp.avg_weight_g > 0) {
            weight = samp.avg_weight_g;
        } else {
            return { status: "NO_DATA", message: "Tidak ada data sampling. Mohon input berat rata-rata ikan (contoh: pakan 105)." };
        }
    }
    
    let fish_count = 8000;
    let survival_rate = 0.9;
    let effective_count = Math.floor(fish_count * survival_rate);
    let rates = getFeedRate(weight);
    let feed_rate_pct = (rates[0] + rates[1]) / 2;
    let total_biomass_kg = (effective_count * weight) / 1000;
    let daily_feed_kg = total_biomass_kg * (feed_rate_pct / 100);
    let min_kg = total_biomass_kg * (rates[0] / 100);
    let max_kg = total_biomass_kg * (rates[1] / 100);
    
    let feed_calc = {
        fish_count_effective: effective_count,
        avg_weight_g: weight,
        total_biomass_kg: parseFloat(total_biomass_kg.toFixed(2)),
        feed_rate_pct: parseFloat(feed_rate_pct.toFixed(2)),
        daily_feed_kg: parseFloat(daily_feed_kg.toFixed(2)),
        feed_range_min_kg: parseFloat(min_kg.toFixed(2)),
        feed_range_max_kg: parseFloat(max_kg.toFixed(2)),
        recommended_rate_range: `${rates[0]}-${rates[1]}%`
    };
    
    let amount_per = daily_feed_kg / 3;
    let sched = [
        {time: "07:00", amount_kg: parseFloat(amount_per.toFixed(2))},
        {time: "12:00", amount_kg: parseFloat(amount_per.toFixed(2))},
        {time: "17:00", amount_kg: parseFloat(amount_per.toFixed(2))}
    ];
    
    let price = getFeedPrice(weight);
    let total_cost = (daily_feed_kg * 7) * price;
    
    let costObj = {
        total_feed_kg: parseFloat((daily_feed_kg * 7).toFixed(2)),
        formatted_cost: `Rp${Math.round(total_cost).toLocaleString('id-ID')}`
    };
    
    return {
        status: "SUCCESS",
        feed_calculation: feed_calc,
        feeding_schedule: sched,
        weekly_cost: costObj
    };
}
