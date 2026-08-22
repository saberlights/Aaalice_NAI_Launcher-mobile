import '../../lib/core/network/nai_api_endpoint.dart';

void main() {
  final chami = NaiApiEndpointConfig.fromInput(
    mainBaseUrl: 'http://chami.yyqzx.com',
  );
  _expect(chami.isChamiRelay, 'Chami host must be detected as a relay');
  _expect(
    chami.imageGenerationUrl() ==
        'http://chami.yyqzx.com/image/chami',
    'Chami generation URL is incorrect',
  );
  _expect(
    !chami.supportsSubscriptionValidation,
    'Chami must not call /user/subscription',
  );
  _expect(
    !chami.supportsImageStream,
    'Chami must use the existing ZIP generation path',
  );

  final fullChamiUrl = NaiApiEndpointConfig.fromInput(
    mainBaseUrl: 'http://chami.yyqzx.com/image/chami',
  );
  _expect(
    fullChamiUrl.imageGenerationUrl() ==
        'http://chami.yyqzx.com/image/chami',
    'Full Chami URL must not have its path appended twice',
  );

  _expect(
    NaiApiEndpointConfig.official.imageGenerationUrl() ==
        'https://image.novelai.net/ai/generate-image',
    'Official NovelAI endpoint behavior changed',
  );
}

void _expect(bool condition, String message) {
  if (!condition) {
    throw StateError(message);
  }
}
