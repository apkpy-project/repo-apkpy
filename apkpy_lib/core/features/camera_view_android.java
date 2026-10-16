package __PACKAGE__;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.util.AttributeSet;
import android.view.*;
import android.widget.*;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.*;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;
import androidx.lifecycle.*;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import org.json.JSONObject;
import java.io.File;
import java.lang.ref.WeakReference;
import java.util.concurrent.*;

/** Embedded, foreground-only photo camera. The host owns its ordinary buttons. */
public final class ApkpyCameraView extends FrameLayout implements DefaultLifecycleObserver {
    public interface CaptureResult { void accept(boolean success,String path); }
    public interface ErrorResult { void accept(String reason); }
    private static WeakReference<ApkpyCameraView> active = new WeakReference<>(null);
    private final PreviewView previewView;
    private final TextView message;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private AppCompatActivity host;
    private ActivityResultLauncher<String> permission;
    private ProcessCameraProvider provider;
    private Preview preview;
    private ImageCapture capture;
    private Camera camera;
    private Runnable onReady;
    private CaptureResult onCapture;
    private ErrorResult onError;
    private String lens="back", flash="off", ratio="4:3";
    private double zoom=1;
    private boolean mirror=true, wanted=true, resumed, ready, busy, destroyed, binding, requesting;
    private int generation;

    public ApkpyCameraView(Context context,AttributeSet attrs){
        super(context,attrs);setBackgroundColor(Color.BLACK);
        previewView=new PreviewView(context);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        addView(previewView,new LayoutParams(-1,-1));
        message=new TextView(context);message.setTextColor(Color.WHITE);message.setTextSize(14);
        message.setGravity(Gravity.CENTER);message.setBackgroundColor(0xcc101820);message.setText("Camera paused");
        addView(message,new LayoutParams(-1,-1));
        previewView.setOnTouchListener((v,e)->{
            if(e.getAction()==MotionEvent.ACTION_UP&&ready&&camera!=null){
                MeteringPoint p=previewView.getMeteringPointFactory().createPoint(e.getX(),e.getY());
                camera.getCameraControl().startFocusAndMetering(new FocusMeteringAction.Builder(p).build());
            }
            return true;
        });
    }
    public void configure(AppCompatActivity activity,String config,Runnable readyCallback,CaptureResult result,ErrorResult error){
        if(host!=null)throw new IllegalStateException("camera_view already configured");
        host=activity;onReady=readyCallback;onCapture=result;onError=error;
        try{
            JSONObject o=new JSONObject(config);lens=o.getString("lens");flash=o.getString("flash");ratio=o.getString("aspect_ratio");
            zoom=o.getDouble("zoom");mirror=o.getBoolean("mirror");wanted=o.getBoolean("autostart");
            previewView.setScaleType(o.getString("fit").equals("contain")?PreviewView.ScaleType.FIT_CENTER:PreviewView.ScaleType.FILL_CENTER);
        }catch(Exception e){wanted=false;fail("invalid_options",false);}
        permission=host.registerForActivityResult(new ActivityResultContracts.RequestPermission(),granted->{
            requesting=false;
            if(destroyed)return;
            if(granted){if(wanted&&resumed)bind();}
            else {wanted=false;fail("permission_denied",false);}
        });
        previewView.getPreviewStreamState().observe(host,state->{
            if(state==PreviewView.StreamState.STREAMING&&camera!=null&&resumed&&wanted&&!ready){
                ready=true;message.setVisibility(GONE);if(onReady!=null)onReady.run();
            }
        });
        host.getLifecycle().addObserver(this);
    }
    private void show(String text){message.setText(text);message.setVisibility(VISIBLE);}
    private void fail(String reason,boolean captureFailure){
        if(destroyed)return;
        if(!ready)show(reason.replace('_',' '));
        if(onError!=null)onError.accept(reason);
        if(captureFailure&&onCapture!=null)onCapture.accept(false,"");
    }
    @Override public void onResume(@NonNull LifecycleOwner owner){resumed=true;if(wanted)post(this::start);}
    @Override public void onPause(@NonNull LifecycleOwner owner){resumed=false;releaseCamera();}
    @Override public void onDestroy(@NonNull LifecycleOwner owner){
        destroyed=true;releaseCamera();io.shutdown();host.getLifecycle().removeObserver(this);
        onReady=null;onCapture=null;onError=null;
    }
    @Override protected void onAttachedToWindow(){super.onAttachedToWindow();if(resumed&&wanted)post(this::start);}
    @Override protected void onDetachedFromWindow(){releaseCamera();super.onDetachedFromWindow();}
    @Override protected void onVisibilityChanged(@NonNull View changed,int visibility){
        super.onVisibilityChanged(changed,visibility);
        if(host!=null&&!destroyed){if(!isShown())releaseCamera();else if(wanted&&resumed)post(this::start);}
    }
    public void start(){
        if(destroyed)return;wanted=true;
        if(!resumed||!isAttachedToWindow()||!isShown()||ready||binding||requesting)return;
        if(ContextCompat.checkSelfPermission(getContext(),Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){
            requesting=true;show("Camera permission required");permission.launch(Manifest.permission.CAMERA);return;
        }
        bind();
    }
    public void stop(){wanted=false;releaseCamera();show("Camera paused");}
    private void releaseCamera(){
        generation++;ready=false;binding=false;busy=false;
        if(camera!=null)camera.getCameraControl().enableTorch(false);
        if(provider!=null){if(preview!=null)provider.unbind(preview);if(capture!=null)provider.unbind(capture);}
        camera=null;preview=null;capture=null;
        if(active.get()==this)active.clear();
    }
    private void bind(){
        if(destroyed||!resumed||!wanted||!isAttachedToWindow())return;
        ApkpyCameraView other=active.get();
        if(other!=null&&other!=this){fail("camera_busy",false);return;}
        releaseCamera();active=new WeakReference<>(this);binding=true;show("Opening camera…");final int revision=generation;
        com.google.common.util.concurrent.ListenableFuture<ProcessCameraProvider> future=ProcessCameraProvider.getInstance(getContext());
        future.addListener(()->{
            if(destroyed||revision!=generation||!resumed||!wanted)return;
            try{
                provider=future.get();CameraSelector selector=new CameraSelector.Builder().requireLensFacing(lens.equals("front")?CameraSelector.LENS_FACING_FRONT:CameraSelector.LENS_FACING_BACK).build();
                if(!provider.hasCamera(selector))throw new IllegalStateException("lens_unavailable");
                int rotation=getDisplay()==null?Surface.ROTATION_0:getDisplay().getRotation();
                int aspect=ratio.equals("16:9")?AspectRatio.RATIO_16_9:AspectRatio.RATIO_4_3;
                preview=new Preview.Builder().setTargetRotation(rotation).setTargetAspectRatio(aspect).build();
                capture=new ImageCapture.Builder().setTargetRotation(rotation).setTargetAspectRatio(aspect).setJpegQuality(95).build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());
                camera=provider.bindToLifecycle(host,selector,preview,capture);binding=false;
                applyFlash();applyZoom();
            }catch(Exception e){releaseCamera();fail(e.getMessage()!=null&&e.getMessage().contains("lens_unavailable")?"lens_unavailable":"camera_unavailable",false);}
        },ContextCompat.getMainExecutor(getContext()));
    }
    private void applyFlash(){if(capture!=null)capture.setFlashMode(flash.equals("auto")?ImageCapture.FLASH_MODE_AUTO:flash.equals("on")?ImageCapture.FLASH_MODE_ON:ImageCapture.FLASH_MODE_OFF);}
    private void applyZoom(){if(camera!=null){ZoomState z=camera.getCameraInfo().getZoomState().getValue();if(z!=null)camera.getCameraControl().setZoomRatio((float)Math.max(z.getMinZoomRatio(),Math.min(z.getMaxZoomRatio(),zoom)));}}
    public void setZoom(double value){if(!Double.isFinite(value)||value<1||value>100){fail("invalid_zoom",false);return;}zoom=value;applyZoom();}
    public void setZoom(String value){try{setZoom(Double.parseDouble(value));}catch(NumberFormatException e){fail("invalid_zoom",false);}}
    public void setFlash(String value){if(!value.equals("off")&&!value.equals("on")&&!value.equals("auto")){fail("invalid_flash",false);return;}flash=value;applyFlash();}
    public void setTorch(boolean enabled){
        if(camera==null||!ready){fail("camera_not_ready",false);return;}
        if(!camera.getCameraInfo().hasFlashUnit()){fail("torch_unavailable",false);return;}
        camera.getCameraControl().enableTorch(enabled);
    }
    public void setTorch(String value){if(!value.equalsIgnoreCase("true")&&!value.equalsIgnoreCase("false")){fail("invalid_torch",false);return;}setTorch(Boolean.parseBoolean(value));}
    public void flip(){if(busy){fail("camera_busy",false);return;}lens=lens.equals("back")?"front":"back";zoom=1;if(resumed&&wanted)bind();}
    public void capture(){
        if(busy){fail("camera_busy",true);return;}
        if(!ready||capture==null||!resumed){fail("camera_not_ready",true);return;}
        busy=true;final int revision=generation;final File file;
        try{
            File dir=new File(getContext().getFilesDir(),"apkpy_camera");
            if(!dir.isDirectory()&&!dir.mkdirs())throw new java.io.IOException();
            file=File.createTempFile("embedded_",".jpg",dir);
        }catch(Exception e){busy=false;fail("storage_unavailable",true);return;}
        ImageCapture.Metadata meta=new ImageCapture.Metadata();meta.setReversedHorizontal(mirror&&lens.equals("front"));
        capture.takePicture(new ImageCapture.OutputFileOptions.Builder(file).setMetadata(meta).build(),io,new ImageCapture.OnImageSavedCallback(){
            public void onImageSaved(@NonNull ImageCapture.OutputFileResults result){
                ContextCompat.getMainExecutor(getContext()).execute(()->{
                    if(destroyed||revision!=generation||!resumed){file.delete();return;}
                    busy=false;
                    try{String uri=FileProvider.getUriForFile(getContext(),getContext().getPackageName()+".fileprovider",file).toString();if(onCapture!=null)onCapture.accept(true,uri);}
                    catch(Exception e){file.delete();fail("storage_unavailable",true);}
                });
            }
            public void onError(@NonNull ImageCaptureException error){file.delete();ContextCompat.getMainExecutor(getContext()).execute(()->{if(destroyed||revision!=generation)return;busy=false;fail("capture_failed",true);});}
        });
    }
}
