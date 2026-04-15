/* eslint-disable @typescript-eslint/no-var-requires */
const path = require('path');
const webpack = require('webpack');
const MonacoWebpackPlugin = require('monaco-editor-webpack-plugin');

const buildTimestamp = new Date().toISOString();

/** Extension host bundle (runs in Node.js) */
const extensionConfig = {
  target: 'node',
  mode: 'none',
  entry: './src/extension.ts',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'extension.js',
    libraryTarget: 'commonjs2',
  },
  externals: {
    vscode: 'commonjs vscode',
  },
  resolve: {
    extensions: ['.ts', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        exclude: /node_modules/,
        use: [{ loader: 'ts-loader' }],
      },
    ],
  },
  plugins: [
    new webpack.DefinePlugin({
      __BUILD_TIMESTAMP__: JSON.stringify(buildTimestamp),
    }),
  ],
  devtool: 'nosources-source-map',
};

/** Webview bundle (runs in browser-like iframe) */
const webviewConfig = {
  target: 'web',
  mode: 'none',
  entry: './webview/editor.ts',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'webview.js',
  },
  resolve: {
    extensions: ['.ts', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        exclude: /node_modules/,
        use: [
          {
            loader: 'ts-loader',
            options: { configFile: 'tsconfig.webview.json' },
          },
        ],
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.ttf$/,
        type: 'asset/resource',
      },
    ],
  },
  plugins: [
    new MonacoWebpackPlugin({
      languages: ['markdown', 'python', 'javascript', 'typescript', 'json', 'yaml', 'html', 'css', 'shell'],
      features: ['find', 'folding', 'hover', 'suggest', 'wordHighlighter', 'bracketMatching'],
    }),
    new webpack.DefinePlugin({
      __BUILD_TIMESTAMP__: JSON.stringify(buildTimestamp),
    }),
  ],
  devtool: 'nosources-source-map',
};

module.exports = [extensionConfig, webviewConfig];
