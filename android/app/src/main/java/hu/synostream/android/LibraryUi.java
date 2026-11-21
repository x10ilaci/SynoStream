package hu.synostream.android;
import android.app.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;

/** Source management is attached to a real library, including the two defaults. */
final class LibraryUi {
    private final MainActivity a;private final SynoApp s;
    LibraryUi(MainActivity activity){a=activity;s=a.s;}
    void create(){
        if(s.busy||s.metadataBusy){a.toast(a.getString(R.string.msg_wait_for_the_scan_to_finish_cc745a));return;}
        try{s.editorReturnPage=s.page;s.libraryDraft=new JSONObject().put("id",UUID.randomUUID().toString()).put("name","").put("movie",true).put("builtin",false).put("paths",new JSONArray());show();}
        catch(JSONException e){a.toast(a.getString(R.string.msg_the_library_could_not_be_created_7ceca4));}
    }
    void edit(JSONObject library){
        if(s.busy||s.metadataBusy){a.toast(a.getString(R.string.msg_wait_for_the_scan_to_finish_cc745a));return;}
        try{s.editorReturnPage=s.page;s.libraryDraft=new JSONObject(library.toString());show();}catch(JSONException e){a.toast(a.getString(R.string.msg_the_library_could_not_be_opened_5eed0e));}
    }
    void sourceSelected(String path){
        if(s.libraryDraft==null)return;
        try{List<String> paths=LibraryConfig.paths(s.libraryDraft);if(!paths.contains(path))paths.add(path);LibraryConfig.paths(s.libraryDraft,paths);s.page=s.editorReturnPage;a.invalidatePage();show();}catch(Exception e){a.toast(a.getString(R.string.msg_the_source_could_not_be_added_e907ea));}
    }
    void cancelBrowse(){s.browseGeneration++;s.busy=false;s.folderLoaded=false;if(s.libraryDraft!=null){s.page=s.editorReturnPage;a.invalidatePage();show();}else{s.page="movies";a.invalidatePage();}}
    void show(){
        if(s.libraryDraft==null||a.isDestroyed())return;JSONObject draft=s.libraryDraft;
        boolean builtin=draft.optBoolean("builtin");Dialog dialog=a.screenDialog();LinearLayout root=a.column();
        LinearLayout bar=a.dialogBar(builtin?a.getString(R.string.msg_library_sources_d7115c):a.getString(R.string.msg_edit_library_ed886a),()->{s.libraryDraft=null;dialog.dismiss();});
        root.addView(bar,a.lp(-1,52));ScrollView scroll=new ScrollView(a);LinearLayout form=a.column();form.setPadding(a.dp(18),a.dp(8),a.dp(18),a.dp(18));scroll.addView(form);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        EditText name=a.input(form,a.getString(R.string.msg_library_name_5c2169),R.id.library_name,false);name.setText(UiText.library(a,draft));name.setEnabled(!builtin);
        RadioGroup types=new RadioGroup(a);types.setOrientation(LinearLayout.HORIZONTAL);
        RadioButton movies=new RadioButton(a);movies.setText(a.getString(R.string.msg_movies_bb20a9));movies.setTextColor(MainActivity.TEXT);movies.setId(View.generateViewId());
        RadioButton shows=new RadioButton(a);shows.setText(a.getString(R.string.msg_tv_shows_8d261b));shows.setTextColor(MainActivity.TEXT);shows.setId(View.generateViewId());types.addView(movies);types.addView(shows);types.check(draft.optBoolean("movie",true)?movies.getId():shows.getId());movies.setEnabled(!builtin);shows.setEnabled(!builtin);form.addView(types,a.lp(-1,48));
        name.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence t,int start,int count,int after){}public void onTextChanged(CharSequence t,int start,int before,int count){try{if(!builtin)draft.put("name",t.toString());}catch(JSONException ignored){}}public void afterTextChanged(android.text.Editable t){}});types.setOnCheckedChangeListener((group,id)->{try{draft.put("movie",id==movies.getId());}catch(JSONException ignored){}});
        form.addView(a.text(a.getString(R.string.msg_nas_source_folders_e6c5b4),18,MainActivity.TEXT),a.lp(-1,44));
        for(String path:LibraryConfig.paths(draft)){
            LinearLayout row=new LinearLayout(a);row.setGravity(Gravity.CENTER_VERTICAL);TextView label=a.text(path,14,MainActivity.MUTED);label.setPadding(0,a.dp(6),a.dp(8),a.dp(6));row.addView(label,new LinearLayout.LayoutParams(0,-2,1));
            View remove=a.icon("remove",a.getString(R.string.msg_remove_source_12bce8),()->{try{List<String> paths=LibraryConfig.paths(draft);paths.remove(path);LibraryConfig.paths(draft,paths);draft.put("name",builtin?draft.optString("name"):name.getText().toString().trim()).put("movie",movies.isChecked());dialog.dismiss();show();}catch(Exception e){a.toast(a.getString(R.string.msg_the_source_could_not_be_removed_cbff0b));}});
            row.addView(remove,a.lp(48,48));form.addView(row,a.lp(-1,-2));
        }
        if(LibraryConfig.paths(draft).isEmpty())form.addView(a.text(a.getString(R.string.msg_no_sources_yet_select_the_movies_or_tv_shows__59c825),15,MainActivity.MUTED),a.lp(-1,-2));
        Button add=a.button(a.getString(R.string.msg_add_source_2dc29c),()->{try{draft.put("name",builtin?draft.optString("name"):name.getText().toString().trim()).put("movie",movies.isChecked());dialog.dismiss();s.page="folders";a.browse("");}catch(Exception e){a.toast(a.getString(R.string.msg_the_folder_picker_could_not_be_opened_8a76a8));}});add.setId(R.id.library_add_source);form.addView(add,a.lp(-1,52));
        Button save=a.button(a.getString(R.string.msg_save_f82013),()->{
            try{
                String title=builtin?draft.optString("name"):name.getText().toString().trim();if(title.isEmpty()){name.setError(a.getString(R.string.msg_enter_a_name_cc021b));return;}
                for(int i=0;i<s.libraries.length();i++){JSONObject existing=s.libraries.optJSONObject(i);if(existing!=null&&!existing.optString("id").equals(draft.optString("id"))&&(MediaLogic.normalize(existing.optString("name")).equals(MediaLogic.normalize(title))||MediaLogic.normalize(UiText.library(a,existing)).equals(MediaLogic.normalize(title)))){name.setError(a.getString(R.string.msg_a_library_with_this_name_already_exists_edit__8b79b0));return;}}
                if(!builtin&&LibraryConfig.paths(draft).isEmpty()){a.toast(a.getString(R.string.msg_add_at_least_one_source_99769f));return;}
                draft.put("name",title).put("movie",movies.isChecked());JSONObject before=LibraryConfig.find(s.libraries,draft.optString("id"));if(CacheKeys.changed(s.identity,before,draft))s.removeCache(before);s.libraries=LibraryConfig.replace(s.libraries,draft);s.store.libraries(s.libraries);s.libraryDraft=null;dialog.dismiss();a.select(draft);
            }catch(Exception e){a.toast(a.getString(R.string.msg_the_library_could_not_be_saved_6d0812));}
        });save.setId(R.id.library_save);root.addView(save,a.lp(-1,54));
        if(!builtin&&LibraryConfig.find(s.libraries,draft.optString("id"))!=null){
            Button delete=a.button(a.getString(R.string.msg_delete_library_ee484b),()->new AlertDialog.Builder(a).setTitle(a.getString(R.string.msg_delete_library_ee484b)).setMessage(a.getString(R.string.msg_only_the_library_configuration_will_be_delete_7da656)).setNegativeButton(a.getString(R.string.msg_cancel_b3e118),null).setPositiveButton(a.getString(R.string.msg_delete_fb437b),(d,w)->{
                s.removeCache(LibraryConfig.find(s.libraries,draft.optString("id")));s.libraries=LibraryConfig.remove(s.libraries,draft.optString("id"));s.store.libraries(s.libraries);s.libraryDraft=null;dialog.dismiss();
                JSONObject replacement=LibraryConfig.defaultLibrary(s.libraries,draft.optBoolean("movie",true));a.select(replacement);
            }).show());delete.setId(R.id.library_delete);form.addView(delete,a.lp(-1,50));
        }
        a.showScreen(dialog,root);
        dialog.setOnCancelListener(d->s.libraryDraft=null);
    }
}
