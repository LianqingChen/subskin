# 生成图像来源和提示词

均由本对话中的内置 image_gen 工具生成，没有输入真人照片。实际模型的训练资料未知，无法确认其是否包含真实白癜风图片；生成图均仅供研究，不能视作真实医学图像。

## train-medium.png

Create a synthetic training background for a machine vision research experiment: a single photorealistic close-up photograph-like view of an entirely fictional adult forearm, skin filling the whole frame edge to edge, medium-brown even pigmentation, realistic fine pores, hair and natural subtle texture, slightly varied diffuse natural daylight. No visible hypopigmentation or depigmentation, no white patches, no lesions, no wounds, no makeup, no marks, no background, no text or watermark. This is an AI-generated fictional surface, not a real person. The image will be paired with automatically generated simulated changes; preserve consistent skin without objects.

## val-light.png

Synthetic dataset image, photorealistic close-up of entirely fictional adult skin, arm or leg skin fills entire frame; light warm beige pigmentation, fine pores and sparse hairs, diffuse daylight and gentle natural spatial lighting. Skin surface intact, no white spots or depigmentation, no patch, no lesion, no wounds, no objects, no text, no watermark. Independent new subject and composition; generated image, not a real photograph.

## test-dark.png

Synthetic dataset image, photorealistic close-up of entirely fictional adult skin, arm or leg skin fills entire frame; deep brown pigmentation with realistic fine skin texture and very sparse hair, indirect warm illumination and soft light gradient. Skin surface intact, no white spots or depigmentation, no patch, no lesion, no wounds, no objects, no text, no watermark. Independent new subject and composition; generated image, not a real photograph.

## direct-unlabeled.png

Research-only wholly AI-synthetic close-up of a fictional adult forearm, skin fills frame. Depict several subtle irregular lighter hypopigmented skin regions of different sizes, with soft varied edges and ordinary skin texture and hair continuing across them, on medium brown surrounding skin under uneven indoor illumination. Natural smartphone-photo-like lighting, no identifying person, no text, no watermark, no medical claims. This is a synthetic illustration for exploring visual variability; do not use real patient photographs or references.

直接生成的图没有匹配掩码，不用于第三轮训练或测试。

## test4-light.png

AI-generated synthetic visual research background, a close-up crop of a fictional adult forearm filling the frame, light warm beige skin with fine pores and sparse hair, softly lit by a window casting an uneven broad gentle shadow across the skin. Natural smartphone-style picture, no visible lesions, no depigmented or white patches, no marks, no background, no text, no watermark. This is a fully fictional person with no real patient photograph or image reference.

## test4-dark.png

AI-generated synthetic visual research background, extreme close-up crop of a fictional adult forearm filling the frame, deep brown skin with natural fine skin texture and sparsely spaced dark hairs, lit by a single indoor lamp with a soft diffuse highlight and a gentle shadow. Natural smartphone-style picture, no visible lesions, no depigmented or white patches, no marks, no background, no text, no watermark. This is a fully fictional person with no real patient photograph or image reference.

## test5-medium.png

Synthetic visual-research background made by AI, close-up of fictional adult forearm filling the entire image, medium tan warm skin tone, natural varied fine skin texture, subtle hair and a diffuse broad soft indoor shadow, photographed as though by a smartphone. No visible depigmented patches, no white spots, no lesions, no scars, no objects, no text, no watermark. Entirely fictional person; no patient photo or input image.

## test6-medium.png

AI generated research background, top-down extreme close-up of a fictional adult upper arm with tan brown intact skin filling entire frame, no background edge. Fine pores and tiny fine hairs, modest light gradient as in indoor smartphone photograph. No white spots, no depigmentation, no visible patches, no lesions, no scars, no objects, no text or watermark. Entirely fictional synthetic person; no patient photographs or input reference.

## test7-medium.png

AI generated synthetic dataset surface: close-up image of a completely fictional adult forearm, medium tan skin completely filling the frame from edge to edge, consistent subtle pores and fine sparse hair, softly diffuse natural daylight with gentle shading, neutral natural color. No white or depigmented patches, no lesions, no scars, no clothing, no background, no objects, no text or watermark. No real person or patient photo used as reference.

## train8-arm.png

Synthetic computer-vision training image of a completely fictional adult forearm with medium warm brown skin and realistic fine pores, crossing horizontally through the center of the frame, wrist and hand outside frame on opposite sides; no other body parts. Arm occupies roughly half the image height. Entire background is a completely uniform vivid cyan blue backdrop, flat and featureless, distinct from skin. Diffuse daylight, subtle natural shading. No white patches, no depigmentation, no lesions, no scars, no jewelry, no text, no watermark. Generated fictional image, no real patient or reference photo.

## test8-arm.png — 候选被排除

Synthetic computer-vision holdout image of a completely fictional adult forearm with light beige skin and realistic fine pores, crossing diagonally through the center of the frame, wrist and hand outside frame; no other body parts. Arm occupies roughly half the image. Entire background is completely uniform vivid cyan blue, flat and featureless, distinct from skin. Soft indoor daylight, gentle natural shadow on the arm, no shadow or objects on backdrop. No white patches, no depigmentation, no lesions, no scars, no jewelry, no text, no watermark. Generated fictional image, no real patient or reference photo.

## test8b-arm.png

Synthetic computer vision holdout: fictional adult light beige forearm spans horizontally through the middle of the landscape image from left to right, completely surrounded above and below by a flat, uniform vivid cyan-blue background. All FOUR image corners are cyan-blue background, with no objects touching any corner. Arm occupies middle 40 percent of image height. Realistic fine skin texture and soft diffuse daylight. No lesions, no white or depigmented patches, no scars, no jewelry, no text or watermark; entirely fictional and no real patient input.

## train9-rejected-nails.png

Synthetic computer vision training image, fictional adult hand seen from above, back of hand facing camera, medium-dark brown skin, hand and wrist entirely inside image, relaxed gently separated five fingers, anatomically natural and realistic fine pores. Solid completely uniform vivid cyan-blue background, all four corners cyan. Soft diffuse lighting. No white patches, no depigmentation, no lesion, no scars, no jewelry, no objects, no text, no watermark. Entirely fictional AI-generated person, no patient or reference photographs.

## test9-rejected-nails.png

Synthetic computer vision holdout image, fictional adult hand viewed from above with back of hand toward camera, light beige skin, whole hand and wrist inside image, relaxed fingers, naturally realistic skin texture. Solid completely uniform vivid cyan-blue background with all four corners cyan. Soft diffuse daylight. No white patches, no depigmentation, no lesion, no scars, no jewelry, no objects, no text, no watermark. Entirely fictional AI-generated person, no patient or reference photographs.

## train9-hand.png

Synthetic computer vision training image of the back of a fictional adult hand with medium-dark brown skin, wrist and lower knuckles only. Crop across the middle of the fingers so NO fingertips or fingernails are visible. Keep entire remaining hand centered and all four corners of the image clear solid vivid cyan-blue background, natural shape with realistic skin texture and soft daylight. No white patches, no depigmentation, no lesions, no scars, no jewelry, no objects, no text, no watermark. Entirely fictional AI-generated person with no real patient image.

## test9-hand.png

Synthetic computer vision holdout image of the back of a fictional adult hand with light beige skin, wrist and lower knuckles only. Crop across the middle of the fingers so NO fingertips or fingernails are visible. Keep entire remaining hand centered and all four corners of the image clear solid vivid cyan-blue background, natural shape with realistic skin texture and soft diffuse daylight. No white patches, no depigmentation, no lesions, no scars, no jewelry, no objects, no text, no watermark. Entirely fictional AI-generated person with no real patient image.

## test10-arm.png

Synthetic vision research holdout: a fictional adult forearm with light brown skin extends horizontally through the center of the landscape image, filling about half its height. Entire background is flat uniform cyan-blue, all four corners clearly cyan, no other objects. Fine skin texture and soft warm indoor light. No white spots, no lesions, no scars, no depigmentation, no jewelry, no text or watermark. AI-created fictional subject, no real patient reference.

## test10-hand.png

Synthetic vision research holdout: back of a fictional adult medium beige hand with wrist and lower knuckles only, fingertips cropped out so no nails are visible. Hand is centered on a flat uniform vivid cyan-blue background with all four corners clearly cyan. Realistic fine skin texture, diffuse window light. No white spots, no lesions, no depigmentation, no scars, no jewelry, no text or watermark. AI-created fictional subject, no real patient reference.

## round11-control.png（以 train8-arm.png 为虚拟输入）

This input is an AI-generated fictional forearm for an image-segmentation experiment. Produce a control edit: reproduce the input image exactly, preserve the arm geometry, all skin pores, hairs, shading, camera position, and the solid cyan background. Do not add or remove any patches or change the apparent skin pigmentation. No text or watermark.

## round11-edited.png（以 train8-arm.png 为虚拟输入）

This input is an AI-generated fictional forearm for an image-segmentation experiment. Add a single subtle irregular depigmented-looking lighter area near the middle of the arm, occupying only a small portion of the visible skin. Preserve the surrounding arm geometry, camera viewpoint, every other region of skin, hair and texture, illumination and the solid cyan background exactly. Keep natural pores and hairs visible through the lighter region. No other changes, text or watermark. This is only a fictional synthetic example, not a real patient photo.

## round12-light-control.png、round12-medium-control.png

This is an AI-generated fictional forearm for research. Control edit: reproduce the image exactly with unchanged geometry, skin texture, color, hairs, lighting and solid cyan background. Do not add or change any pale region. No watermark or text.

## round12-light-edited.png、round12-medium-edited.png

This is an AI-generated fictional forearm for image-analysis research. Add two distinct irregular hypopigmented-looking areas, one larger and one much smaller, separated on the center-left and center-right of the forearm. Preserve all other skin, hairs, geometry, camera angle, illumination and cyan background as exactly as possible. No text or watermark, no real patient photo.

## test15-light.png

Synthetic computer-vision holdout image of a fictional adult forearm with light beige skin horizontally across the center, skin occupies the middle half, all four corners are clear uniform vivid cyan-blue background. Realistic fine pores, natural gentle daylight. No depigmentation, no white patches, no lesions, no scars, no jewelry, no words or watermark. Completely AI-created, no real patient photographs or reference.

## test15-dark.png

Synthetic computer-vision holdout image of a fictional adult forearm with deep brown skin horizontally across the center, skin occupies the middle half, all four corners are clear uniform vivid cyan-blue background. Realistic fine pores, soft natural indoor lighting. No depigmentation, no white patches, no lesions, no scars, no jewelry, no words or watermark. Completely AI-created, no real patient photographs or reference.

## test16-dark.png

AI-generated synthetic research holdout, entirely fictional adult forearm with medium warm brown skin, horizontal across the center of frame, all four corners and background flat uniform vivid cyan blue. Natural fine pores and sparse hair, diffuse light. No depigmentation, no white patches, no lesions or scars, no jewelry, no text or watermark. No real patient image or reference.

## test16-light.png

AI-generated synthetic research holdout, entirely fictional adult forearm with fair beige skin, horizontal across the center of frame, all four corners and background flat uniform vivid cyan blue. Natural fine pores and sparse hair, soft diffused indoor light. No depigmentation, no white patches, no lesions or scars, no jewelry, no text or watermark. No real patient image or reference.

## test16-dark.png

AI-generated synthetic research holdout, entirely fictional adult forearm with medium warm brown skin, horizontal across the center of frame, all four corners and background flat uniform vivid cyan blue. Natural fine pores and sparse hair, diffuse light. No depigmentation, no white patches, no lesions or scars, no jewelry, no text or watermark. No real patient image or reference.

## test16-light.png

AI-generated synthetic research holdout, entirely fictional adult forearm with fair beige skin, horizontal across the center of frame, all four corners and background flat uniform vivid cyan blue. Natural fine pores and sparse hair, soft diffused indoor light. No depigmentation, no white patches, no lesions or scars, no jewelry, no text or watermark. No real patient image or reference.

## test17-arm.png

Synthetic computer vision holdout image: fictional adult forearm, medium brown skin, horizontally across image center, all four corners and surrounding background flat uniform cyan blue. Fine pores, subtle sparse hair, diffuse daylight. No skin depigmentation, no white areas, no lesions, no scars, no jewelry, no text, no watermark. Completely AI-created, no real patient or reference photo.

## test17-hand.png

Synthetic computer vision holdout image: back of fictional adult hand, light beige skin, wrist and lower knuckles only, fingertips cropped out and no fingernails visible; image corners are all flat uniform cyan blue. Soft diffuse lighting, realistic pores. No skin depigmentation, no white patches, no lesions, no scars, no jewelry, no text, no watermark. Completely AI-created, no real patient or reference photo.

## test18-person-medium.png

Synthetic research-only image of a completely fictional adult person, front-facing head and upper torso visible, medium brown skin, wearing an opaque short-sleeve dark navy T-shirt with both bare forearms naturally visible, no logos. Simple evenly lit cyan background, natural smartphone-style photo. Skin has no visible white patches, no lesions or scars. No text, no watermark. Do not reference or depict any actual patient or real person.

## test18-person-light.png

Synthetic research-only image of a completely fictional adult person, front-facing head and upper torso visible, light beige skin, wearing an opaque short-sleeve charcoal T-shirt with both bare forearms naturally visible, no logos. Simple evenly lit cyan background, natural smartphone-style photo. Skin has no visible white patches, no lesions or scars. No text, no watermark. Do not reference or depict any actual patient or real person.

## test19-arm.png

Synthetic computer vision dataset holdout: a completely fictional adult forearm with warm medium-brown skin extends horizontally through the center of a landscape image. All four corners and the empty background are uniformly vivid cyan blue. Fine skin texture and natural diffuse light. No white patches, no lesions, no scars, no depigmentation, no jewelry, no words or watermark. No real patient or reference image.

## test19-hand.png

Synthetic computer vision dataset holdout: back of a completely fictional adult hand with light beige skin, showing wrist and lower knuckles only, finger tips outside frame and no fingernails visible; all four corners of the frame and the background are uniformly vivid cyan blue. Fine skin texture and soft diffuse natural light. No white patches, no lesions, no depigmentation, no scars, no jewelry, no text or watermark. No real patient or reference image.

## test20-arm.png

Synthetic research holdout image of a completely fictional adult forearm with olive brown skin, extending horizontally across the middle of a landscape frame, all four corners and background flat uniform vivid cyan blue. Fine skin texture, diffuse indoor light. No white or pale patches, no depigmentation, no lesions, no scars, no jewelry, no text or watermark. Entirely AI-created, no actual patient photo or reference.

## test20-hand.png

Synthetic research holdout image of the back of a completely fictional adult hand with warm medium brown skin, wrist and lower knuckles only, fingertips cropped out and no fingernails visible; all four image corners and background flat uniform vivid cyan blue. Fine skin texture and soft natural daylight. No white or pale patches, no lesions, no depigmentation, no scars, no jewelry, no text or watermark. Entirely AI-created, no actual patient photo or reference.

## test21-arm.png

Synthetic research holdout image, completely fictional adult forearm with warm medium skin extends horizontally in the middle of a landscape frame. All four corners and empty background are flat vivid cyan blue. Fine pores and diffuse soft daylight. No white or pale patches, no depigmentation, no lesions or scars, no jewelry, no text, no watermark. Entirely AI-created; no patient or real-person reference.

## test21-hand.png

Synthetic research holdout image, back of a completely fictional adult hand with light beige skin, wrist and lower knuckles only, fingertips cropped out so no fingernails are visible. All four image corners and background are flat vivid cyan blue. Fine skin texture and diffuse daylight. No white or pale patches, no depigmentation, no lesions or scars, no jewelry, no text, no watermark. Entirely AI-created; no patient or real-person reference.

## Round 22：独立虚拟测试底图

- Arm: Synthetic computer vision holdout, fictional adult forearm with warm medium-brown skin crossing horizontally through image center, all four corners and empty background flat vivid cyan-blue. Fine skin pores, sparse hair, diffuse natural lighting. No depigmentation, white patches, lesions, scars, jewelry, text or watermark. Entirely AI-generated, no real patient or reference photo.
- Hand: Synthetic computer vision holdout, back of a fictional adult hand with light beige skin, wrist and lower knuckles only; fingertips cropped out and no fingernails visible. Entire background and all four image corners flat vivid cyan-blue. Fine skin texture and diffuse daylight. No depigmentation, white patches, lesions, scars, jewelry, text or watermark. Entirely AI-generated, no real patient or reference photo.

## Round 24：训练与保留测试的虚拟底图

- `train24-arm.png`: Synthetic computer vision training background, AI-created fictional adult forearm with dark brown skin, crossing horizontally through center, sparse fine hairs, even light, realistic skin pores. Entire backdrop and all four corners flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, jewelry, text or watermark. No real patient or reference photo.
- `train24-hand.png`: Synthetic computer vision training background, AI-created fictional adult hand back with medium brown skin, wrist and lower knuckles only, fingers and nails cropped out, detailed skin texture, soft diffuse light. Entire background and all four image corners flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, jewelry, text or watermark. No real patient or reference photo.
- `test24-arm.png`: Synthetic computer vision test background, AI-created fictional adult forearm with light beige skin, crossing horizontally through center, fine realistic skin texture, soft diffuse light. Entire backdrop and all four corners flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, jewelry, text or watermark. No real patient or reference photo.
- `test24-hand.png`: Synthetic computer vision test background, AI-created fictional adult hand back with dark brown skin, wrist and lower knuckles only, fingers and nails cropped out, detailed realistic skin texture, diffuse natural light. Entire background and all four image corners flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, jewelry, text or watermark. No real patient or reference photo.

## Round 28：虚拟保留测试底图

- `test28-arm.png`: AI-generated synthetic research test image, fictional adult forearm with olive medium skin passing horizontally through the center, gentle diffuse light and natural texture. All four corners and the entire empty background are flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, text, jewelry or watermark. No real patient or reference photograph.
- `test28-hand.png`: AI-generated synthetic research test image, back of a fictional adult hand with medium warm brown skin, wrist and lower knuckles only, fingers and nails outside image. Gentle diffuse light, realistic fine texture. All four corners and entire background flat vivid cyan-blue. No white patches, lesions, depigmentation, scars, text, jewelry or watermark. No real patient or reference photograph.

## Round 33：色差梯度虚拟保留底图

- `test33-arm.png`: Synthetic computer vision holdout, AI-generated fictional adult forearm of medium dark brown skin, crossing horizontally through image center, fine natural skin texture and hair, diffuse lighting. Background and all four corners flat vivid cyan-blue. No white patches, depigmentation, scars, wounds, jewelry, text or watermark. No real patient or reference photo.
- `test33-hand.png`: Synthetic computer vision holdout, AI-generated fictional adult hand back, light tan skin, wrist and lower knuckles only, fingertips and nails cropped out, soft diffuse light and fine texture. Background and all four corners flat vivid cyan-blue. No white patches, depigmentation, scars, wounds, jewelry, text or watermark. No real patient or reference photo.

## Round 34：独立色差测试虚拟底图

- `test34-arm.png`: Synthetic research image, AI-generated fictional adult forearm, warm medium brown skin, horizontally across image center, visible fine hair and skin texture, soft diffuse illumination, no white patches, depigmentation, scars, jewelry, text or watermark. Entire background and all four corners are flat vivid cyan blue. No real patient or reference photograph.
- `test34-hand.png`: Synthetic research image, AI-generated fictional adult hand back with light beige skin, wrist and lower knuckles only, fingertips and nails out of frame, gentle diffuse lighting, no white patches, depigmentation, scars, jewelry, text or watermark. Entire background and all four corners flat vivid cyan blue. No real patient or reference photograph.

## Round 37：预训练编码器对照测试底图

- `test37-arm.png`: AI-generated synthetic visual benchmark: fictional adult forearm with medium brown skin, horizontal across center, fine natural hair and texture, gentle diffuse illumination. All four corners and background flat vivid cyan-blue. No white patches, depigmentation, scars, jewelry, text or watermark. No real patient or reference photograph.
- `test37-hand.png`: AI-generated synthetic visual benchmark: fictional adult hand back with light tan skin, wrist and lower knuckles only, fingertips and nails cropped out, natural texture, diffuse light. All four corners and background flat vivid cyan-blue. No white patches, depigmentation, scars, jewelry, text or watermark. No real patient or reference photograph.

## Round 40：独立色差测试虚拟底图

- `test40-arm.png`: AI-generated synthetic research benchmark, fictional adult forearm with medium dark brown skin across image horizontally, fine hair and skin texture, diffuse daylight, no white patches, depigmentation, scars, jewelry, text or watermark. Entire background and all four corners flat vivid cyan blue. No real patient or reference photograph.
- `test40-hand.png`: AI-generated synthetic research benchmark, fictional adult hand back with light beige skin, wrist and lower knuckles only, fingertips and nails cropped out, realistic texture and diffuse daylight, no white patches, depigmentation, scars, jewelry, text or watermark. Entire background and all four corners flat vivid cyan blue. No real patient or reference photograph.

## Round 46：连通域过滤的独立虚拟测试底图

- `test46-arm.png`: AI-generated synthetic research benchmark, fictional adult forearm with medium warm brown skin, horizontally across the image, natural fine hair and texture, soft diffuse light. All four corners and whole background flat vivid cyan-blue. No white patches, depigmentation, scars, jewelry, text or watermark. No real patient or reference photograph.
- `test46-hand.png`: AI-generated synthetic research benchmark, fictional adult hand back with light beige skin, wrist and lower knuckles only, fingertips and nails cropped out, natural fine texture and diffuse daylight. All four corners and whole background flat vivid cyan-blue. No white patches, depigmentation, scars, jewelry, text or watermark. No real patient or reference photograph.

## Round 51：两种颜色合成机制的虚拟测试底图

- `test51-leg.png`: AI-generated fictional adult lower leg, medium brown skin, side view of shin and calf stretching horizontally across image center, fine pores and sparse hair, diffuse natural lighting. All four corners and entire background flat vivid cyan-blue. No patches, depigmentation, scars, injuries, shoes, text or watermark. Synthetic research image, no real patient or reference photo.
- `test51-hand.png`: AI-generated fictional adult hand back, light beige skin, wrist and lower knuckles only, fingers and fingernails outside image, fine skin texture, soft diffuse lighting. All four corners and entire background flat vivid cyan-blue. No patches, depigmentation, scars, jewelry, text or watermark. Synthetic research image, no real patient or reference photo.
