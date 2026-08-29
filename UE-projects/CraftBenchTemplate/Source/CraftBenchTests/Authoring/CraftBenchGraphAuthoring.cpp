// Copyright CraftBench. All Rights Reserved.
//
// VERIFIER-ONLY MODULE — DO NOT EDIT.
// AUTHORING-ONLY: see CraftBenchGraphAuthoring.h for the full policy note.
// No grader, layer or fixture may reference this translation unit.

#include "Authoring/CraftBenchGraphAuthoring.h"

#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "GameFramework/Actor.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

DEFINE_LOG_CATEGORY_STATIC(LogCraftBenchAuthoring, Log, All);

namespace
{
	/** Fail-loud helper: one named reason per precondition, always returns false. */
	bool AuthoringFail(const TCHAR* Reason, const FString& Context)
	{
		UE_LOG(LogCraftBenchAuthoring, Error,
			TEXT("CRAFTBENCH-AUTHORING FAILED reason=%s context=%s"), Reason, *Context);
		return false;
	}

	const TCHAR* BeginPlayEventName = TEXT("ReceiveBeginPlay");
}

bool UCraftBenchGraphAuthoring::AddBeginPlayCallNode(UBlueprint* Blueprint, UClass* FunctionOwnerClass, FName FunctionName)
{
	if (Blueprint == nullptr)
	{
		return AuthoringFail(TEXT("NULL_BLUEPRINT"), TEXT("<none>"));
	}
	const FString BlueprintName = Blueprint->GetPathName();

	if (FunctionOwnerClass == nullptr)
	{
		return AuthoringFail(TEXT("NULL_FUNCTION_OWNER_CLASS"), BlueprintName);
	}
	if (FunctionName.IsNone())
	{
		return AuthoringFail(TEXT("EMPTY_FUNCTION_NAME"), BlueprintName);
	}

	// The function must actually exist on the owner class. Without this the
	// call node would still be created, but with zero pins and a dangling
	// member reference — i.e. it would look authored and ship nothing.
	const UFunction* TargetFunction = FunctionOwnerClass->FindFunctionByName(FunctionName);
	if (TargetFunction == nullptr)
	{
		return AuthoringFail(TEXT("FUNCTION_NOT_FOUND_ON_CLASS"),
			FString::Printf(TEXT("%s :: %s::%s"), *BlueprintName,
				*FunctionOwnerClass->GetName(), *FunctionName.ToString()));
	}

	UEdGraph* Graph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
	if (Graph == nullptr && Blueprint->UbergraphPages.Num() > 0)
	{
		Graph = Blueprint->UbergraphPages[0];
	}
	if (Graph == nullptr)
	{
		return AuthoringFail(TEXT("NO_EVENT_GRAPH"), BlueprintName);
	}

	// --- Event BeginPlay -------------------------------------------------- //
	UK2Node_Event* BeginPlayNode = nullptr;
	for (UEdGraphNode* Node : Graph->Nodes)
	{
		UK2Node_Event* EventNode = Cast<UK2Node_Event>(Node);
		if (EventNode != nullptr && EventNode->EventReference.GetMemberName() == FName(BeginPlayEventName))
		{
			BeginPlayNode = EventNode;
			break;
		}
	}
	if (BeginPlayNode == nullptr)
	{
		int32 NodePosY = 0;
		BeginPlayNode = FKismetEditorUtilities::AddDefaultEventNode(
			Blueprint, Graph, FName(BeginPlayEventName), AActor::StaticClass(), NodePosY);
	}
	if (BeginPlayNode == nullptr)
	{
		return AuthoringFail(TEXT("NO_BEGINPLAY_NODE"), BlueprintName);
	}

	// --- The call node ---------------------------------------------------- //
	UK2Node_CallFunction* CallNode = NewObject<UK2Node_CallFunction>(Graph);
	if (CallNode == nullptr)
	{
		return AuthoringFail(TEXT("CALL_NODE_ALLOC_FAILED"), BlueprintName);
	}
	CallNode->FunctionReference.SetExternalMember(FunctionName, FunctionOwnerClass);
	Graph->AddNode(CallNode, /*bFromUI=*/false, /*bSelectNewNode=*/false);
	CallNode->CreateNewGuid();
	CallNode->PostPlacedNewNode();
	CallNode->AllocateDefaultPins();
	CallNode->NodePosX = BeginPlayNode->NodePosX + 420;
	CallNode->NodePosY = BeginPlayNode->NodePosY;

	// --- Wire exec (BeginPlay.then -> Call.exec) --------------------------- //
	UEdGraphPin* ThenPin = BeginPlayNode->FindPin(UEdGraphSchema_K2::PN_Then, EGPD_Output);
	if (ThenPin == nullptr)
	{
		return AuthoringFail(TEXT("NO_BEGINPLAY_THEN_PIN"), BlueprintName);
	}
	UEdGraphPin* CallExecPin = CallNode->GetExecPin();
	if (CallExecPin == nullptr)
	{
		return AuthoringFail(TEXT("NO_CALL_EXEC_PIN"),
			FString::Printf(TEXT("%s :: %s"), *BlueprintName, *FunctionName.ToString()));
	}
	ThenPin->MakeLinkTo(CallExecPin);
	if (!ThenPin->LinkedTo.Contains(CallExecPin))
	{
		return AuthoringFail(TEXT("EXEC_LINK_NOT_ESTABLISHED"), BlueprintName);
	}

	// Non-exec input pins keep their literal defaults on purpose — the row
	// wants "called with a literal argument", not a wired argument chain.

	// --- Compile ----------------------------------------------------------- //
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status != BS_UpToDate)
	{
		return AuthoringFail(TEXT("COMPILE_NOT_CLEAN"),
			FString::Printf(TEXT("%s status=%d"), *BlueprintName, static_cast<int32>(Blueprint->Status)));
	}

	// --- Save --------------------------------------------------------------- //
	UPackage* Package = Blueprint->GetOutermost();
	if (Package == nullptr)
	{
		return AuthoringFail(TEXT("NO_PACKAGE"), BlueprintName);
	}
	Package->MarkPackageDirty();

	const FString PackageFileName = FPackageName::LongPackageNameToFilename(
		Package->GetName(), FPackageName::GetAssetPackageExtension());

	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;
	SaveArgs.Error = GError;
	if (!UPackage::SavePackage(Package, nullptr, *PackageFileName, SaveArgs))
	{
		return AuthoringFail(TEXT("SAVE_PACKAGE_FAILED"),
			FString::Printf(TEXT("%s -> %s"), *BlueprintName, *PackageFileName));
	}

	UE_LOG(LogCraftBenchAuthoring, Display,
		TEXT("CRAFTBENCH-AUTHORING OK blueprint=%s call=%s::%s saved=%s"),
		*BlueprintName, *FunctionOwnerClass->GetName(), *FunctionName.ToString(), *PackageFileName);
	return true;
}
