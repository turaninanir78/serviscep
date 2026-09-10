const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// expo-router, app/ altindaki HER dosyayi (test dosyalari dahil) bir route
// adayi olarak taramaya calisiyor - *.test.tsx dosyalari @jest/globals import
// ettigi icin bu, web bundle'inda "Do not import @jest/globals outside of
// the Jest test environment" hatasiyla tum uygulamanin cokmesine yol aciyordu.
// Bu, Jest'in kendi test calistirmasini ETKILEMIYOR (Jest bu dosyayi degil,
// kendi resolver'ini kullanir) - sadece Metro'nun (native/web bundle) bu
// dosyalari route/modul olarak gormesini engelliyor.
const existingBlockList = config.resolver.blockList
  ? Array.isArray(config.resolver.blockList)
    ? config.resolver.blockList
    : [config.resolver.blockList]
  : [];

config.resolver.blockList = [...existingBlockList, /\.test\.[jt]sx?$/];

module.exports = config;
