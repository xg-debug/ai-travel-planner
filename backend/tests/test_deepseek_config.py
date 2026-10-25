import unittest
from unittest.mock import Mock, call, patch

from fastapi import HTTPException
from app.api.admin import LLMSettingsUpdate, RuntimeSettingsUpdate, update_settings
from app.core.llm import LLMFactory
from app.services.runtime_config import get_llm_model, normalize_llm_model


class DeepSeekConfigTests(unittest.TestCase):
    def test_current_models_are_selectable_and_legacy_flash_is_upgraded(self):
        self.assertEqual(normalize_llm_model("deepseek", "deepseek-flash"), "deepseek-flash")
        self.assertEqual(normalize_llm_model("deepseek", "deepseek-v4-pro"), "deepseek-v4-pro")
        self.assertEqual(normalize_llm_model("deepseek", "deepseek-v4-flash"), "deepseek-flash")
        self.assertEqual(normalize_llm_model("deepseek", "deepseek-chat"), "deepseek-flash")

    def test_saved_pro_model_is_not_forced_back_to_flash(self):
        with patch("app.services.runtime_config.get_runtime_setting", side_effect=lambda key: "deepseek-v4-pro" if key == "llm.deepseek.model" else None):
            self.assertEqual(get_llm_model("deepseek"), "deepseek-v4-pro")

    def test_deepseek_uses_official_openai_compatible_base_url(self):
        with patch("app.core.llm.get_llm_api_key", return_value="real-unit-key"), \
                patch("langchain_openai.ChatOpenAI") as chat:
            LLMFactory.create_llm(provider="deepseek", model="deepseek-v4-pro")
        self.assertEqual(chat.call_args.kwargs["base_url"], "https://api.deepseek.com")
        self.assertEqual(chat.call_args.kwargs["model"], "deepseek-v4-pro")

    def test_admin_can_save_pro_and_reject_unknown_deepseek_model(self):
        principal = Mock()
        principal.user.id = "admin-test"
        db = Mock()
        with patch("app.api.admin.set_setting_value") as save, \
                patch("app.api.admin.build_runtime_config_snapshot", return_value={}):
            update_settings(
                RuntimeSettingsUpdate(llm=LLMSettingsUpdate(provider="deepseek", model="deepseek-v4-pro")),
                principal=principal,
                db=db,
            )
            self.assertIn(call(db, "llm.deepseek.model", "deepseek-v4-pro", "admin-test"), save.call_args_list)
            with self.assertRaises(HTTPException) as error:
                update_settings(
                    RuntimeSettingsUpdate(llm=LLMSettingsUpdate(provider="deepseek", model="deepseek-unknown")),
                    principal=principal,
                    db=db,
                )
            self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
